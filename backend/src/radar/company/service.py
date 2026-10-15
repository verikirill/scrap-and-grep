"""Company spaces: teams, the accounts made for their people, invitations.

A manager makes a space, describes the teams and lists the people. Each
person gets an account with the team's profile already in it and a link that
lets them set a password and come in. Nothing else is asked of them.
"""

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
from radar.company.roles import (
    HeuristicTeamDrafter,
    ResilientTeamDrafter,
    TeamBrief,
    TeamDrafter,
    member_spec,
)
from radar.db.models import Company, Profile, Team, User
from radar.domain import ProfileSpec

# 192 random bits: a link cannot be guessed.
_INVITE_BYTES = 24
INVITE_TTL_DAYS = 14
MAX_TEAMS = 50
MAX_MEMBERS_PER_TEAM = 300


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
        return Membership(company=owned.name, team=None, role="owner")
    row = (
        await session.execute(
            select(Company.name, Team.name, User.job_title, Company.owner_id)
            .select_from(User)
            .join(Team, Team.id == User.team_id)
            .join(Company, Company.id == Team.company_id)
            .where(User.id == user_id)
        )
    ).one_or_none()
    if row is None:
        return None
    manager = await session.scalar(select(User.display_name).where(User.id == row[3]))
    return Membership(company=row[0], team=row[1], role="member", job_title=row[2], manager=manager)


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


async def follow_team(session: AsyncSession, team: Team) -> list[uuid.UUID]:
    """Give the team's current profile to every member profile that still
    follows it, and return whose profiles changed. A profile its reader edited
    no longer follows, and keeps the edit. The look stays the reader's."""
    spec = ProfileSpec.model_validate(team.spec)
    rows = (
        await session.execute(
            select(Profile, User.job_title)
            .join(User, User.id == Profile.user_id)
            .where(Profile.team_id == team.id)
        )
    ).all()
    changed: list[uuid.UUID] = []
    for profile, job_title in rows:
        personal = member_spec(spec, job_title).model_dump(mode="json")
        if personal != profile.spec:
            profile.spec = personal
            profile.name = spec.name
            profile.version += 1
            changed.append(profile.user_id)
    await session.flush()
    return changed


async def move_profiles(session: AsyncSession, user: User, source: uuid.UUID, target: Team) -> None:
    """A member changed team or position: the profiles that follow the team are
    worded anew; the reader's own profiles stay as they are."""
    spec = member_spec(ProfileSpec.model_validate(target.spec), user.job_title)
    await session.execute(
        update(Profile)
        .where(Profile.user_id == user.id, Profile.team_id == source)
        .values(
            team_id=target.id,
            name=spec.name,
            spec=spec.model_dump(mode="json"),
            icon=target.icon,
            color=target.color,
            version=Profile.version + 1,
        )
    )


async def add_members(
    session: AsyncSession, team: Team, people: Sequence[Person]
) -> tuple[list[User], list[Skipped]]:
    """Make an account with the team's profile for each person.

    An address that is already registered is skipped, not taken over: the
    space cannot reach into an account someone made for themselves. The
    unique index decides, so two managers adding one address cannot both win.
    """
    spec = ProfileSpec.model_validate(team.spec)
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
        user = await session.scalar(
            insert(User)
            .values(
                email=email,
                display_name=(person.name.strip() or email.split("@")[0])[:80],
                avatar_preset=random_preset(),
                team_id=team.id,
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
        personal = member_spec(spec, job_title)
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
