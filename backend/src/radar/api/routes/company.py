"""A company space: its teams, their profiles and the accounts of their people."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
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
    SkippedOut,
    TeamDraftIn,
    TeamDraftOut,
    TeamIn,
    TeamOut,
)
from radar.api.deps import CacheDep, CurrentUser, SessionDep, user_rate_limit
from radar.auth import sessions as auth_sessions
from radar.auth.sessions import AuthUser
from radar.avatars import preset_for
from radar.company import service
from radar.company.roles import audience_for, team_color, team_icon
from radar.db.models import Company, ForgottenReader, Team, User
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


def member_out(user: User, now: datetime | None = None) -> MemberOut:
    now = now or datetime.now(UTC)
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
        audience=audience_for(user.job_title),
        status=member_status,
        invite_path=f"/invite/{user.invite_token}" if member_status == "invited" else None,
        invite_expires_at=user.invite_expires_at if member_status == "invited" else None,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def team_out(team: Team, members: list[User]) -> TeamOut:
    return TeamOut(
        id=team.id,
        name=team.name,
        services=team.services,
        spec=ProfileSpec.model_validate(team.spec),
        icon=team.icon,
        color=team.color,
        members=[member_out(member) for member in members],
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


async def _company_out(session: SessionDep, company: Company) -> CompanyOut:
    teams = await service.company_teams(session, company.id)
    members = await service.team_members(session, [team.id for team in teams])
    by_team: dict[uuid.UUID, list[User]] = {team.id: [] for team in teams}
    for member in members:
        if member.team_id in by_team:
            by_team[member.team_id].append(member)
    return CompanyOut(
        id=company.id,
        name=company.name,
        about=company.about,
        teams=[team_out(team, by_team[team.id]) for team in teams],
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
    return TeamDraftOut(spec=spec, icon=team_icon(brief.as_text()), drafted_by=drafter.name)


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
    text = service.brief_for(company, payload.name, payload.services, payload.systems).as_text()
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
    return team_out(team, [])


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
    out = team_out(team, await service.team_members(session, [team.id]))
    if changed:
        # Commit first, then let the cached tastes go, as a profile edit does.
        await session.commit()
        for member_id in set(changed):
            await forget_taste(cache, member_id)
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
    created, skipped = await service.add_members(session, team, people)
    log.info("company_members_added", created=len(created), skipped=len(skipped))
    now = datetime.now(UTC)
    return MembersAddedOut(
        created=[member_out(member, now) for member in created],
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
    """Another team, a new position or name. The profiles that follow the team
    are worded anew; profiles the person made or edited stay theirs."""
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
    reworded = target.id != source or payload.job_title is not None
    if reworded:
        member.team_id = target.id
        await service.move_profiles(session, member, source, target)
    await session.flush()
    await session.refresh(member)
    out = member_out(member)
    if reworded:
        # Commit first, then let the cached taste go, as a profile edit does.
        await session.commit()
        await forget_taste(cache, member.id)
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
    return member_out(member)


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
