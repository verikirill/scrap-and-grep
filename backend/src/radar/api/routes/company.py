"""A company space: its teams, their profiles and the accounts of their people."""

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from radar.api.company_schemas import (
    CompanyIn,
    CompanyOut,
    CompanyPatch,
    MemberOut,
    MemberPatch,
    MembersAddedOut,
    MembersIn,
    MoveIn,
    PatchIn,
    PatchOut,
    RoleDraftIn,
    RoleIn,
    RoleOut,
    SkippedOut,
    TeamDraftIn,
    TeamDraftOut,
    TeamIn,
    TeamOut,
)
from radar.api.deps import CacheDep, CurrentUser, SessionDep, user_rate_limit
from radar.api.uploads import read_limited
from radar.auth import sessions as auth_sessions
from radar.auth.sessions import AuthUser
from radar.avatars import MAX_BYTES as LOGO_MAX_BYTES
from radar.avatars import AvatarError, normalize, normalize_logo, preset_for
from radar.company import service
from radar.company.patches import PatchError
from radar.company.roles import team_color, team_icon
from radar.db.models import Company, ForgottenReader, Team, TeamRole, User
from radar.domain import ProfileSpec
from radar.events import enabled as events_enabled
from radar.logging import get_logger
from radar.recsys.service import forget_taste

router = APIRouter(prefix="/company", tags=["company"])
log = get_logger(__name__)

_write_limit = Depends(user_rate_limit("write", lambda settings: settings.rate_limit_per_minute))
# A draft is a question to the model: as many a minute as questions to a digest.
_draft_limit = Depends(
    user_rate_limit("team-draft", lambda settings: settings.ask_rate_limit_per_minute)
)

_NO_COMPANY = "Пространство компании ещё не создано."
_NO_TEAM = "Команда не найдена."
_NO_MEMBER = "Сотрудник не найден."
_NO_ROLE = "Роль не найдена."
# Redrawing a picture costs CPU: a few at a time.
_DRAWING = asyncio.Semaphore(2)
_picture_limit = Depends(
    user_rate_limit("avatar", lambda settings: settings.resume_rate_limit_per_minute)
)


def member_out(
    user: User, team: Team, roles: dict[uuid.UUID, TeamRole], now: datetime | None = None
) -> MemberOut:
    now = now or datetime.now(UTC)
    role = roles.get(user.role_id) if user.role_id else None
    spec = service.personal_spec(service.source_spec(team, role), user)
    if user.password_hash is not None:
        member_status = "active"
    elif user.invite_token and user.invite_expires_at and user.invite_expires_at > now:
        member_status = "invited"
    else:
        member_status = "expired"
    return MemberOut(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        job_title=user.job_title,
        avatar_preset=preset_for(user.id, user.avatar_preset),
        team_id=user.team_id,
        role_id=role.id if role else None,
        overrides=len(user.profile_overrides or []),
        audience=spec.audience,
        status=member_status,
        invite_path=f"/invite/{user.invite_token}" if member_status == "invited" else None,
        invite_expires_at=user.invite_expires_at if member_status == "invited" else None,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def role_out(role: TeamRole) -> RoleOut:
    return RoleOut(
        id=role.id,
        name=role.name,
        description=role.description,
        spec=ProfileSpec.model_validate(role.spec),
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def team_out(team: Team, members: list[User], roles: list[TeamRole]) -> TeamOut:
    by_id = {role.id: role for role in roles}
    now = datetime.now(UTC)
    return TeamOut(
        id=team.id,
        name=team.name,
        services=team.services,
        spec=ProfileSpec.model_validate(team.spec),
        icon=team.icon,
        color=team.color,
        picture_url=(
            f"/api/v1/company/teams/{team.id}/picture?v={int(team.picture_updated_at.timestamp())}"
            if team.picture_updated_at
            else None
        ),
        roles=[role_out(role) for role in roles],
        members=[member_out(member, team, by_id, now) for member in members],
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


async def _company(session: SessionDep, user: AuthUser) -> Company:
    company = await service.owned_company(session, user.id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_COMPANY)
    return company


async def _team(session: SessionDep, company: Company, team_id: uuid.UUID) -> Team:
    team = await service.owned_team(session, company, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_TEAM)
    return team


async def _member(session: SessionDep, company: Company, user_id: uuid.UUID) -> User:
    member = await service.owned_member(session, company, user_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_MEMBER)
    return member


async def _team_view(session: SessionDep, team: Team) -> TeamOut:
    members = await service.team_members(session, [team.id])
    return team_out(team, members, await service.team_roles(session, [team.id]))


async def _member_view(session: SessionDep, member: User, team: Team) -> MemberOut:
    roles = await service.team_roles(session, [team.id])
    return member_out(member, team, {role.id: role for role in roles})


async def _member_team(session: SessionDep, company: Company, member: User) -> Team:
    """The team a member was found through."""
    if member.team_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_MEMBER)
    return await _team(session, company, member.team_id)


async def _role(session: SessionDep, team: Team, role_id: uuid.UUID) -> TeamRole:
    role = await service.owned_role(session, team, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_ROLE)
    return role


async def _forget(session: SessionDep, cache: CacheDep, changed: list[uuid.UUID]) -> None:
    """Commit first, then let the cached tastes go, as a profile edit does."""
    if changed:
        await session.commit()
        for member_id in set(changed):
            await forget_taste(cache, member_id)


async def _company_out(session: SessionDep, company: Company) -> CompanyOut:
    teams = await service.company_teams(session, company.id)
    team_ids = [team.id for team in teams]
    members = await service.team_members(session, team_ids)
    roles = await service.team_roles(session, team_ids)
    by_team: dict[uuid.UUID, list[User]] = {team.id: [] for team in teams}
    for member in members:
        if member.team_id in by_team:
            by_team[member.team_id].append(member)
    roles_of: dict[uuid.UUID, list[TeamRole]] = {team.id: [] for team in teams}
    for role in roles:
        roles_of[role.team_id].append(role)
    return CompanyOut(
        id=company.id,
        name=company.name,
        about=company.about,
        logo_url=service.logo_url(company.logo_updated_at),
        teams=[team_out(team, by_team[team.id], roles_of[team.id]) for team in teams],
        created_at=company.created_at,
    )


@router.get("")
async def get_company(session: SessionDep, user: CurrentUser) -> CompanyOut | None:
    """The space this account manages; `null` while there is none."""
    company = await service.owned_company(session, user.id)
    return await _company_out(session, company) if company else None


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[_write_limit])
async def create_company(payload: CompanyIn, session: SessionDep, user: CurrentUser) -> CompanyOut:
    if user.is_demo:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Пространство компании доступно после регистрации.",
        )
    if await service.is_member(session, user.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Ваш аккаунт уже входит в команду компании.",
        )
    if await service.owned_company(session, user.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Пространство компании уже есть.")
    company = Company(owner_id=user.id, name=payload.name.strip(), about=payload.about.strip())
    session.add(company)
    try:
        await session.flush()
    except IntegrityError as exc:
        # A second request of the same manager got there first.
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Пространство компании уже есть."
        ) from exc
    await session.refresh(company)
    log.info("company_created", company_id=str(company.id))
    return await _company_out(session, company)


@router.patch("", dependencies=[_write_limit])
async def update_company(
    payload: CompanyPatch, session: SessionDep, user: CurrentUser
) -> CompanyOut:
    company = await _company(session, user)
    if payload.name is not None:
        company.name = payload.name.strip()
    if payload.about is not None:
        company.about = payload.about.strip()
    await session.flush()
    return await _company_out(session, company)


@router.post("/teams/draft", dependencies=[_draft_limit])
async def draft_team(payload: TeamDraftIn, session: SessionDep, user: CurrentUser) -> TeamDraftOut:
    """The profile the description suggests, for the manager to check before
    saving. Nothing is stored."""
    company = await _company(session, user)
    brief = service.brief_for(company, payload.name, payload.services, payload.systems)
    drafter = service.get_drafter()
    spec = await drafter.draft(brief)
    return TeamDraftOut(spec=spec, icon=team_icon(brief.own_text()), drafted_by=drafter.name)


async def _team_spec(company: Company, payload: TeamIn) -> ProfileSpec:
    spec = payload.spec
    if spec is None:
        brief = service.brief_for(company, payload.name, payload.services, payload.systems)
        spec = await service.get_drafter().draft(brief)
    # The profile is named after the team, whatever the draft said.
    return ProfileSpec.model_validate({**spec.model_dump(mode="json"), "name": payload.name})


@router.post("/teams", status_code=status.HTTP_201_CREATED, dependencies=[_draft_limit])
async def create_team(payload: TeamIn, session: SessionDep, user: CurrentUser) -> TeamOut:
    company = await _company(session, user)
    count = await service.count_teams(session, company.id)
    if count >= service.MAX_TEAMS:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Слишком много команд.")
    spec = await _team_spec(company, payload)
    text = service.brief_for(company, payload.name, payload.services, payload.systems).own_text()
    team = Team(
        company_id=company.id,
        name=payload.name.strip(),
        services=payload.services.strip(),
        spec=spec.model_dump(mode="json"),
        icon=payload.icon or team_icon(text),
        color=payload.color or team_color(count),
    )
    session.add(team)
    await session.flush()
    await session.refresh(team)
    return team_out(team, [], [])


@router.put("/teams/{team_id}", dependencies=[_draft_limit])
async def update_team(
    team_id: uuid.UUID,
    payload: TeamIn,
    session: SessionDep,
    cache: CacheDep,
    user: CurrentUser,
) -> TeamOut:
    """Change the team; the member profiles that still follow it change too."""
    company = await _company(session, user)
    team = await _team(session, company, team_id)
    spec = await _team_spec(company, payload)
    team.name = payload.name.strip()
    team.services = payload.services.strip()
    team.spec = spec.model_dump(mode="json")
    if payload.icon:
        team.icon = payload.icon
    if payload.color:
        team.color = payload.color
    await session.flush()
    changed = await service.follow_team(session, team)
    await session.refresh(team)
    out = await _team_view(session, team)
    await _forget(session, cache, changed)
    return out


@router.delete(
    "/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_write_limit]
)
async def delete_team(team_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    company = await _company(session, user)
    team = await _team(session, company, team_id)
    if await service.team_members(session, [team.id]):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="В команде есть сотрудники: сначала переведите их в другую команду или удалите.",
        )
    await session.delete(team)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/teams/{team_id}/members",
    status_code=status.HTTP_201_CREATED,
    dependencies=[_write_limit],
)
async def add_members(
    team_id: uuid.UUID, payload: MembersIn, session: SessionDep, user: CurrentUser
) -> MembersAddedOut:
    """Accounts with the team's profile for the people listed, each with an
    invitation link. Addresses that already have an account are skipped."""
    company = await _company(session, user)
    team = await _team(session, company, team_id)
    people = [
        service.Person(name=person.name, email=person.email, job_title=person.job_title)
        for person in payload.people
    ]
    role = await _role(session, team, payload.role_id) if payload.role_id else None
    created, skipped = await service.add_members(session, team, people, role)
    log.info("company_members_added", created=len(created), skipped=len(skipped))
    roles = {item.id: item for item in await service.team_roles(session, [team.id])}
    now = datetime.now(UTC)
    return MembersAddedOut(
        created=[member_out(member, team, roles, now) for member in created],
        skipped=[SkippedOut(email=item.email, reason=item.reason) for item in skipped],
    )


@router.patch("/members/{user_id}", dependencies=[_write_limit])
async def update_member(
    user_id: uuid.UUID,
    payload: MemberPatch,
    session: SessionDep,
    cache: CacheDep,
    user: CurrentUser,
) -> MemberOut:
    """Another team or role, a new position or name. The profiles that follow
    the team are made anew; profiles the person made or edited stay theirs."""
    company = await _company(session, user)
    member = await _member(session, company, user_id)
    # Found through their team, so the team is there.
    source = member.team_id
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_MEMBER)
    target = await _team(session, company, payload.team_id or source)
    if payload.display_name is not None:
        member.display_name = payload.display_name.strip()
    if payload.job_title is not None:
        member.job_title = payload.job_title.strip() or None
    if "role_id" in payload.model_fields_set:
        role = await _role(session, target, payload.role_id) if payload.role_id else None
        member.role_id = role.id if role else None
    elif target.id != source:
        # Roles belong to a team: in the new one, the role the position names.
        roles = await service.team_roles(session, [target.id])
        matched = service.match_role(member.job_title, roles)
        member.role_id = matched.id if matched else None
    member.team_id = target.id
    await service.refresh_member(session, member, source, target)
    await session.flush()
    await session.refresh(member)
    out = await _member_view(session, member, target)
    await _forget(session, cache, [member.id])
    return out


@router.post("/members/move", dependencies=[_write_limit])
async def move_members(
    payload: MoveIn, session: SessionDep, cache: CacheDep, user: CurrentUser
) -> list[MemberOut]:
    """Several people to another team at once, as the manager dragged them."""
    company = await _company(session, user)
    target = await _team(session, company, payload.team_id)
    roles = await service.team_roles(session, [target.id])
    moved: list[User] = []
    for member_id in dict.fromkeys(payload.member_ids):
        member = await _member(session, company, member_id)
        source = member.team_id
        if source is None or source == target.id:
            continue
        matched = service.match_role(member.job_title, roles)
        member.role_id = matched.id if matched else None
        member.team_id = target.id
        await service.refresh_member(session, member, source, target)
        moved.append(member)
    await session.flush()
    by_id = {role.id: role for role in roles}
    out = []
    for member in moved:
        await session.refresh(member)
        out.append(member_out(member, target, by_id))
    await _forget(session, cache, [member.id for member in moved])
    return out


@router.delete("/members/{user_id}/overrides", dependencies=[_write_limit])
async def reset_overrides(
    user_id: uuid.UUID, session: SessionDep, cache: CacheDep, user: CurrentUser
) -> MemberOut:
    """Drop the changes made for this person alone: back to the team's or role's profile."""
    company = await _company(session, user)
    member = await _member(session, company, user_id)
    team = await _member_team(session, company, member)
    member.profile_overrides = []
    await service.refresh_member(session, member, team.id, team)
    await session.flush()
    out = await _member_view(session, member, team)
    await _forget(session, cache, [member.id])
    return out


@router.post("/members/{user_id}/invite", dependencies=[_write_limit])
async def renew_invite(user_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> MemberOut:
    """A fresh link for someone who has not come in yet; the old one stops working."""
    company = await _company(session, user)
    member = await _member(session, company, user_id)
    if member.password_hash is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Сотрудник уже вошёл и входит со своим паролем.",
        )
    member.invite_token, member.invite_expires_at = service.new_invite()
    await session.flush()
    return await _member_view(session, member, await _member_team(session, company, member))


@router.delete(
    "/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_write_limit]
)
async def remove_member(
    user_id: uuid.UUID, session: SessionDep, cache: CacheDep, user: CurrentUser
) -> Response:
    """Delete the account the space made, with everything in it, as when a
    person leaves the company."""
    company = await _company(session, user)
    member = await _member(session, company, user_id)
    await auth_sessions.end_all(session, cache, member.id)
    await session.execute(delete(User).where(User.id == member.id))
    if events_enabled():
        session.add(ForgottenReader(user_id=member.id))
    await session.commit()
    await forget_taste(cache, member.id)
    log.info("company_member_removed", user_id=str(member.id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/teams/{team_id}/roles/draft", dependencies=[_draft_limit])
async def draft_role(
    team_id: uuid.UUID, payload: RoleDraftIn, session: SessionDep, user: CurrentUser
) -> TeamDraftOut:
    """The profile a role's description suggests, read with the team's. Nothing is stored."""
    company = await _company(session, user)
    team = await _team(session, company, team_id)
    systems = ProfileSpec.model_validate(team.spec).systems
    brief = service.brief_for(
        company,
        f"{team.name}: {payload.name}",
        f"{team.services}\n{payload.description}".strip(),
        systems[:20],
    )
    drafter = service.get_drafter()
    spec = await drafter.draft(brief)
    return TeamDraftOut(
        spec=service.role_spec(team, payload.name, spec),
        icon=team.icon or team_icon(brief.own_text()),
        drafted_by=drafter.name,
    )


@router.post(
    "/teams/{team_id}/roles", status_code=status.HTTP_201_CREATED, dependencies=[_write_limit]
)
async def create_role(
    team_id: uuid.UUID, payload: RoleIn, session: SessionDep, cache: CacheDep, user: CurrentUser
) -> RoleOut:
    """A role within the team. Without a checked profile it starts as the team's.
    People whose position names it and who have no role yet get it at once."""
    company = await _company(session, user)
    team = await _team(session, company, team_id)
    if len(await service.team_roles(session, [team.id])) >= service.MAX_ROLES_PER_TEAM:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Слишком много ролей в команде.")
    base = payload.spec or ProfileSpec.model_validate(team.spec)
    role = TeamRole(
        team_id=team.id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        spec=service.role_spec(team, payload.name, base).model_dump(mode="json"),
    )
    session.add(role)
    await session.flush()
    await session.refresh(role)
    for member in await service.team_members(session, [team.id]):
        if member.role_id is None and service.match_role(member.job_title, [role]):
            member.role_id = role.id
    await session.flush()
    changed = await service.follow_team(session, team)
    out = role_out(role)
    await _forget(session, cache, changed)
    return out


@router.put("/teams/{team_id}/roles/{role_id}", dependencies=[_write_limit])
async def update_role(
    team_id: uuid.UUID,
    role_id: uuid.UUID,
    payload: RoleIn,
    session: SessionDep,
    cache: CacheDep,
    user: CurrentUser,
) -> RoleOut:
    """Change the role; its people's profiles change too, unless they made theirs their own."""
    company = await _company(session, user)
    team = await _team(session, company, team_id)
    role = await _role(session, team, role_id)
    base = payload.spec or ProfileSpec.model_validate(role.spec)
    role.name = payload.name.strip()
    role.description = payload.description.strip()
    role.spec = service.role_spec(team, payload.name, base).model_dump(mode="json")
    await session.flush()
    changed = await service.follow_team(session, team)
    await session.refresh(role)
    out = role_out(role)
    await _forget(session, cache, changed)
    return out


@router.delete(
    "/teams/{team_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_write_limit],
)
async def delete_role(
    team_id: uuid.UUID, role_id: uuid.UUID, session: SessionDep, cache: CacheDep, user: CurrentUser
) -> Response:
    """Its people go back to the team's profile."""
    company = await _company(session, user)
    team = await _team(session, company, team_id)
    role = await _role(session, team, role_id)
    for member in await service.team_members(session, [team.id]):
        if member.role_id == role.id:
            member.role_id = None
    await session.delete(role)
    await session.flush()
    await _forget(session, cache, await service.follow_team(session, team))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/teams/{team_id}/patch", dependencies=[_write_limit])
async def patch_profiles(
    team_id: uuid.UUID, payload: PatchIn, session: SessionDep, cache: CacheDep, user: CurrentUser
) -> PatchOut:
    """One change for the whole team, for one role, or for chosen people.

    For the team or a role the change goes into their profile. For people it
    is kept with each of them and survives later changes of the team.
    """
    company = await _company(session, user)
    team = await _team(session, company, team_id)
    if payload.patch.is_empty():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Изменений нет.")
    try:
        if payload.scope == "team":
            changed = await service.patch_team(session, team, payload.patch)
        elif payload.scope == "role":
            if payload.role_id is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Выберите роль.")
            role = await _role(session, team, payload.role_id)
            changed = await service.patch_role(session, team, role, payload.patch)
        else:
            people = [
                await _member(session, company, member_id)
                for member_id in dict.fromkeys(payload.member_ids)
            ]
            if not people or any(person.team_id != team.id for person in people):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Выберите сотрудников этой команды.",
                )
            changed = await service.patch_people(session, team, people, payload.patch)
    except PatchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    await _forget(session, cache, changed)
    return PatchOut(changed=len(set(changed)))


@router.put("/logo", dependencies=[_picture_limit])
async def set_logo(request: Request, session: SessionDep, user: CurrentUser) -> CompanyOut:
    """The company's logo: JPEG, PNG, WebP or GIF up to 5 MB, redrawn as a
    small WebP in its own proportions."""
    company = await _company(session, user)
    data = await read_limited(
        request, LOGO_MAX_BYTES, "Размер файла превышает 5 МБ. Выберите картинку поменьше."
    )
    try:
        async with _DRAWING:
            logo = await asyncio.to_thread(normalize_logo, data)
    except AvatarError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    company.logo = logo
    company.logo_updated_at = datetime.now(UTC)
    await session.flush()
    return await _company_out(session, company)


@router.delete("/logo", dependencies=[_write_limit])
async def delete_logo(session: SessionDep, user: CurrentUser) -> CompanyOut:
    company = await _company(session, user)
    company.logo = None
    company.logo_updated_at = None
    await session.flush()
    return await _company_out(session, company)


@router.get("/logo")
async def get_logo(session: SessionDep, user: CurrentUser) -> Response:
    """The logo of the space this account manages or was made for. The address
    carries the logo's time, so the browser may keep it for good."""
    company = await service.company_of(session, user.id)
    logo = await service.logo_of(session, company.id) if company else None
    if logo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Логотипа нет.")
    return Response(
        content=logo,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )


@router.put("/teams/{team_id}/picture", dependencies=[_picture_limit])
async def set_team_picture(
    team_id: uuid.UUID, request: Request, session: SessionDep, user: CurrentUser
) -> TeamOut:
    """A picture of the team's own in place of its icon: squared, a small WebP."""
    company = await _company(session, user)
    team = await _team(session, company, team_id)
    data = await read_limited(
        request, LOGO_MAX_BYTES, "Размер файла превышает 5 МБ. Выберите картинку поменьше."
    )
    try:
        async with _DRAWING:
            picture = await asyncio.to_thread(normalize, data)
    except AvatarError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    team.picture = picture
    team.picture_updated_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(team)
    return await _team_view(session, team)


@router.delete("/teams/{team_id}/picture", dependencies=[_write_limit])
async def delete_team_picture(
    team_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> TeamOut:
    company = await _company(session, user)
    team = await _team(session, company, team_id)
    team.picture = None
    team.picture_updated_at = None
    await session.flush()
    await session.refresh(team)
    return await _team_view(session, team)


@router.get("/teams/{team_id}/picture")
async def get_team_picture(team_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    """The picture of a team of the space this account manages or belongs to."""
    company = await service.company_of(session, user.id)
    team = await service.owned_team(session, company, team_id) if company else None
    picture = await service.team_picture(session, team.id) if team else None
    if picture is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Картинки нет.")
    return Response(
        content=picture,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )
