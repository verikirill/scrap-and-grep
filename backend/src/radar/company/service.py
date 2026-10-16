"""Company spaces: teams, the accounts made for their people, invitations.

A manager makes a space, describes the teams and lists the people. Each
person gets an account with the team's profile already in it and a link that
lets them set a password and come in. Nothing else is asked of them.
"""

import re
import secrets
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.ai.factory import get_breaker, get_chat
from radar.auth.passwords import hash_password
from radar.auth.service import normalize_email
from radar.avatars import random_preset
from radar.company.patches import (
    MAX_PERSONAL_PATCHES,
    ProfilePatch,
    apply_all,
    apply_patch,
)
from radar.company.roles import (
    HeuristicTeamDrafter,
    ResilientTeamDrafter,
    TeamBrief,
    TeamDrafter,
    member_spec,
)
from radar.db.models import Company, Profile, Team, TeamRole, User
from radar.domain import ProfileSpec

# 192 random bits: a link cannot be guessed.
_INVITE_BYTES = 24
INVITE_TTL_DAYS = 14
MAX_TEAMS = 50
MAX_MEMBERS_PER_TEAM = 300
MAX_ROLES_PER_TEAM = 20


@lru_cache
def get_drafter() -> TeamDrafter:
    fallback = HeuristicTeamDrafter()
    chat = get_chat()
    if chat is None:
        return fallback

    from radar.company.roles import ModelTeamDrafter

    return ResilientTeamDrafter(ModelTeamDrafter(chat), fallback, get_breaker())


@dataclass(frozen=True, slots=True)
class Person:
    """One line of the manager's list."""

    name: str
    email: str
    job_title: str = ""


@dataclass(frozen=True, slots=True)
class Skipped:
    email: str
    reason: str


@dataclass(frozen=True, slots=True)
class Membership:
    """Where an account stands in a company space."""

    company: str
    team: str | None
    role: str  # "owner" or "member"
    job_title: str | None = None
    manager: str | None = None
    # When the company's logo was set; None without one.
    logo_at: datetime | None = None


def logo_url(logo_at: datetime | None) -> str | None:
    """Where the logo is served: its time in the address, so a new one is
    fetched at once and an old one can be cached for good."""
    return f"/api/v1/company/logo?v={int(logo_at.timestamp())}" if logo_at else None


def new_invite() -> tuple[str, datetime]:
    return secrets.token_urlsafe(_INVITE_BYTES), datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS)


async def owned_company(session: AsyncSession, owner_id: uuid.UUID) -> Company | None:
    return await session.scalar(select(Company).where(Company.owner_id == owner_id))


async def company_teams(session: AsyncSession, company_id: uuid.UUID) -> list[Team]:
    rows = await session.scalars(
        select(Team).where(Team.company_id == company_id).order_by(Team.created_at, Team.id)
    )
    return list(rows)


async def team_members(session: AsyncSession, team_ids: Sequence[uuid.UUID]) -> list[User]:
    if not team_ids:
        return []
    rows = await session.scalars(
        select(User).where(User.team_id.in_(team_ids)).order_by(User.created_at, User.id)
    )
    return list(rows)


async def owned_team(session: AsyncSession, company: Company, team_id: uuid.UUID) -> Team | None:
    return await session.scalar(
        select(Team).where(Team.id == team_id, Team.company_id == company.id)
    )


async def owned_member(session: AsyncSession, company: Company, user_id: uuid.UUID) -> User | None:
    """A person of this company's teams; anyone else is reported as missing."""
    return await session.scalar(
        select(User)
        .join(Team, Team.id == User.team_id)
        .where(User.id == user_id, Team.company_id == company.id)
    )


async def is_member(session: AsyncSession, user_id: uuid.UUID) -> bool:
    return (await session.scalar(select(User.team_id).where(User.id == user_id))) is not None


async def membership(session: AsyncSession, user_id: uuid.UUID) -> Membership | None:
    owned = await owned_company(session, user_id)
    if owned is not None:
        return Membership(
            company=owned.name, team=None, role="owner", logo_at=owned.logo_updated_at
        )
    row = (
        await session.execute(
            select(
                Company.name, Team.name, User.job_title, Company.owner_id, Company.logo_updated_at
            )
            .select_from(User)
            .join(Team, Team.id == User.team_id)
            .join(Company, Company.id == Team.company_id)
            .where(User.id == user_id)
        )
    ).one_or_none()
    if row is None:
        return None
    manager = await session.scalar(select(User.display_name).where(User.id == row[3]))
    return Membership(
        company=row[0],
        team=row[1],
        role="member",
        job_title=row[2],
        manager=manager,
        logo_at=row[4],
    )


async def company_of(session: AsyncSession, user_id: uuid.UUID) -> Company | None:
    """The space an account manages, or else the one it was made for."""
    owned = await owned_company(session, user_id)
    if owned is not None:
        return owned
    return await session.scalar(
        select(Company)
        .join(Team, Team.company_id == Company.id)
        .join(User, User.team_id == Team.id)
        .where(User.id == user_id)
    )


def brief_for(company: Company, name: str, services: str, systems: Sequence[str] = ()) -> TeamBrief:
    return TeamBrief(
        company=company.name,
        about=company.about,
        team=name,
        services=services,
        systems=tuple(systems),
    )


async def count_teams(session: AsyncSession, company_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count()).select_from(Team).where(Team.company_id == company_id)
    )
    return int(count or 0)


async def team_roles(session: AsyncSession, team_ids: Sequence[uuid.UUID]) -> list[TeamRole]:
    if not team_ids:
        return []
    rows = await session.scalars(
        select(TeamRole)
        .where(TeamRole.team_id.in_(team_ids))
        .order_by(TeamRole.created_at, TeamRole.id)
    )
    return list(rows)


async def owned_role(session: AsyncSession, team: Team, role_id: uuid.UUID) -> TeamRole | None:
    return await session.scalar(
        select(TeamRole).where(TeamRole.id == role_id, TeamRole.team_id == team.id)
    )


def source_spec(team: Team, role: TeamRole | None) -> ProfileSpec:
    """What a member starts from: their role's profile, or else the team's."""
    return ProfileSpec.model_validate(role.spec if role is not None else team.spec)


def personal_spec(source: ProfileSpec, user: User) -> ProfileSpec:
    """A member's copy: worded for the position, with the manager's changes
    for this person laid over it."""
    return apply_all(member_spec(source, user.job_title), user.profile_overrides or [])


_WORD_RE = re.compile(r"\w+")
# A word of a role's name stands for its forms: «аналитик» finds «аналитика».
_STEM = 6
_MIN_WORD = 4


def match_role(job_title: str | None, roles: Sequence[TeamRole]) -> TeamRole | None:
    """The role a position names, by its long words: «ведущий аналитик SOC»
    gets the role «Аналитик ИБ». The role with most words found wins."""
    if not job_title or not roles:
        return None
    words = [word.casefold() for word in _WORD_RE.findall(job_title)]
    best: tuple[int, TeamRole | None] = (0, None)
    for role in roles:
        stems = [
            word.casefold()[:_STEM]
            for word in _WORD_RE.findall(role.name)
            if len(word) >= _MIN_WORD
        ]
        if not stems or not all(any(w.startswith(stem) for w in words) for stem in stems):
            continue
        if len(stems) > best[0]:
            best = (len(stems), role)
    return best[1]


async def follow_team(session: AsyncSession, team: Team) -> list[uuid.UUID]:
    """Give every member profile that still follows the team what its member
    should have now: the role's or the team's profile with their own changes.
    Returns whose profiles changed. A profile its reader edited no longer
    follows, and keeps the edit. The look stays the reader's."""
    roles = {role.id: role for role in await team_roles(session, [team.id])}
    rows = (
        await session.execute(
            select(Profile, User)
            .join(User, User.id == Profile.user_id)
            .where(Profile.team_id == team.id)
        )
    ).all()
    changed: list[uuid.UUID] = []
    for profile, user in rows:
        role = roles.get(user.role_id) if user.role_id else None
        spec = personal_spec(source_spec(team, role), user)
        personal = spec.model_dump(mode="json")
        if personal != profile.spec:
            profile.spec = personal
            profile.name = spec.name
            profile.version += 1
            changed.append(profile.user_id)
    await session.flush()
    return changed


async def refresh_member(
    session: AsyncSession, user: User, source: uuid.UUID, target: Team
) -> None:
    """A member changed team, role, position or own changes: the profiles that
    follow the team are made anew; the reader's own profiles stay as they are."""
    role = await owned_role(session, target, user.role_id) if user.role_id else None
    spec = personal_spec(source_spec(target, role), user)
    look = {"icon": target.icon, "color": target.color} if source != target.id else {}
    await session.execute(
        update(Profile)
        .where(Profile.user_id == user.id, Profile.team_id == source)
        .values(
            team_id=target.id,
            name=spec.name,
            spec=spec.model_dump(mode="json"),
            version=Profile.version + 1,
            **look,
        )
    )


def role_spec(team: Team, name: str, spec: ProfileSpec) -> ProfileSpec:
    """A role's profile is named after the team and the role: «SOC: аналитик»."""
    title = f"{team.name}: {name.strip()}"[:120]
    return ProfileSpec.model_validate({**spec.model_dump(mode="json"), "name": title})


async def patch_team(session: AsyncSession, team: Team, patch: ProfilePatch) -> list[uuid.UUID]:
    """One change for the whole team: its profile and every role's."""
    team.spec = apply_patch(ProfileSpec.model_validate(team.spec), patch).model_dump(mode="json")
    for role in await team_roles(session, [team.id]):
        role.spec = apply_patch(ProfileSpec.model_validate(role.spec), patch).model_dump(
            mode="json"
        )
    await session.flush()
    return await follow_team(session, team)


async def patch_role(
    session: AsyncSession, team: Team, role: TeamRole, patch: ProfilePatch
) -> list[uuid.UUID]:
    role.spec = apply_patch(ProfileSpec.model_validate(role.spec), patch).model_dump(mode="json")
    await session.flush()
    return await follow_team(session, team)


async def patch_people(
    session: AsyncSession, team: Team, people: Sequence[User], patch: ProfilePatch
) -> list[uuid.UUID]:
    """One change kept with each chosen person, over their team's or role's
    profile: a later change of the team does not undo it."""
    roles = {role.id: role for role in await team_roles(session, [team.id])}
    for user in people:
        # Refused as a whole if it does not fit even one of them.
        role = roles.get(user.role_id) if user.role_id else None
        apply_patch(personal_spec(source_spec(team, role), user), patch)
    raw = patch.model_dump(mode="json", exclude_defaults=True)
    for user in people:
        user.profile_overrides = [*(user.profile_overrides or []), raw][-MAX_PERSONAL_PATCHES:]
    await session.flush()
    return await follow_team(session, team)


async def add_members(
    session: AsyncSession, team: Team, people: Sequence[Person], role: TeamRole | None = None
) -> tuple[list[User], list[Skipped]]:
    """Make an account with the team's profile for each person. Everyone gets
    the role given; without one, the role their position names, if any.

    An address that is already registered is skipped, not taken over: the
    space cannot reach into an account someone made for themselves. The
    unique index decides, so two managers adding one address cannot both win.
    """
    roles = await team_roles(session, [team.id])
    present = await session.scalar(
        select(func.count()).select_from(User).where(User.team_id == team.id)
    )
    room = MAX_MEMBERS_PER_TEAM - int(present or 0)
    created: list[User] = []
    skipped: list[Skipped] = []
    seen: set[str] = set()
    for person in people:
        email = normalize_email(person.email)
        if email is None:
            skipped.append(Skipped(person.email, "Проверьте адрес почты."))
            continue
        if email in seen:
            skipped.append(Skipped(email, "Адрес повторяется в списке."))
            continue
        seen.add(email)
        if len(created) >= room:
            skipped.append(Skipped(email, "В команде уже слишком много людей."))
            continue
        token, expires_at = new_invite()
        job_title = person.job_title.strip()[:120] or None
        assigned = role or match_role(job_title, roles)
        user = await session.scalar(
            insert(User)
            .values(
                email=email,
                display_name=(person.name.strip() or email.split("@")[0])[:80],
                avatar_preset=random_preset(),
                team_id=team.id,
                role_id=assigned.id if assigned else None,
                job_title=job_title,
                invite_token=token,
                invite_expires_at=expires_at,
            )
            .on_conflict_do_nothing(index_elements=["email"])
            .returning(User)
        )
        if user is None:
            skipped.append(Skipped(email, "С этой почтой уже есть аккаунт."))
            continue
        personal = personal_spec(source_spec(team, assigned), user)
        session.add(
            Profile(
                user_id=user.id,
                name=personal.name,
                spec=personal.model_dump(mode="json"),
                icon=team.icon,
                color=team.color,
                team_id=team.id,
            )
        )
        created.append(user)
    await session.flush()
    return created, skipped


async def invited(session: AsyncSession, token: str) -> User | None:
    """The account an unused, unexpired invitation is for."""
    return await session.scalar(
        select(User).where(
            User.invite_token == token,
            User.invite_expires_at > datetime.now(UTC),
            # Only an account nobody has entered yet: a link never replaces
            # a password its owner chose.
            User.password_hash.is_(None),
            User.is_demo.is_(False),
        )
    )


async def accept(session: AsyncSession, token: str, password: str) -> User | None:
    """Set the first password; the link stops working at once. Two requests
    with one link cannot both win: the update itself checks the link is unused."""
    password_hash = await hash_password(password)
    return await session.scalar(
        update(User)
        .where(
            User.invite_token == token,
            User.invite_expires_at > datetime.now(UTC),
            User.password_hash.is_(None),
            User.is_demo.is_(False),
        )
        .values(password_hash=password_hash, invite_token=None, invite_expires_at=None)
        .returning(User)
    )


async def logo_of(session: AsyncSession, company_id: uuid.UUID) -> bytes | None:
    return await session.scalar(select(Company.logo).where(Company.id == company_id))
