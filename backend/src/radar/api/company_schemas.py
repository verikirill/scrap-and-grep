"""Request and response models of a company space (radar.company)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from radar.auth.passwords import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from radar.avatars import AvatarPreset
from radar.company.patches import ProfilePatch
from radar.domain import Audience, ProfileSpec

SystemName = Annotated[str, Field(min_length=1, max_length=80)]
LookKey = Annotated[str, Field(min_length=1, max_length=24, pattern=r"^[a-z#0-9-]+$")]


class CompanyIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    about: str = Field(default="", max_length=2000)


class CompanyPatch(BaseModel):
    """The fields to change; those left out stay as they are."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    about: str | None = Field(default=None, max_length=2000)


class TeamDraftIn(BaseModel):
    """What the manager wrote about a team: the model reads it."""

    name: str = Field(min_length=2, max_length=120)
    services: str = Field(default="", max_length=3000)
    systems: list[SystemName] = Field(default=[], max_length=20)


class TeamDraftOut(BaseModel):
    spec: ProfileSpec
    icon: str
    # The model's name, or "taxonomy" when the table of areas made the draft.
    drafted_by: str


class TeamIn(TeamDraftIn):
    # The draft the manager checked; without one the service drafts it itself.
    spec: ProfileSpec | None = None
    icon: LookKey | None = None
    color: LookKey | None = None


MemberStatus = Literal["invited", "expired", "active"]


class MemberOut(BaseModel):
    id: uuid.UUID
    display_name: str
    email: str
    job_title: str | None
    avatar_preset: AvatarPreset
    team_id: uuid.UUID | None
    role_id: uuid.UUID | None = None
    # How many changes the manager made for this person alone.
    overrides: int = 0
    # What their copy of the team's profile reads: the cards or the brief.
    audience: Audience
    # "invited": the link works; "expired": a new one is needed; "active":
    # the person set a password and came in.
    status: MemberStatus
    # Where the person sets a password, while the link works: /invite/<token>.
    invite_path: str | None = None
    invite_expires_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime


class RoleDraftIn(BaseModel):
    """A role within a team, in the manager's words: the model reads it with
    the team's description."""

    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=2000)


class RoleIn(RoleDraftIn):
    # The profile the manager checked; without one the team's is the start.
    spec: ProfileSpec | None = None


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    spec: ProfileSpec
    created_at: datetime
    updated_at: datetime


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str
    services: str
    spec: ProfileSpec
    icon: str | None
    color: str | None
    roles: list[RoleOut] = []
    members: list[MemberOut]
    created_at: datetime
    updated_at: datetime


class CompanyOut(BaseModel):
    id: uuid.UUID
    name: str
    about: str
    # Where the logo is served; a new one gets a new address. Null without one.
    logo_url: str | None = None
    teams: list[TeamOut]
    created_at: datetime


class PersonIn(BaseModel):
    name: str = Field(default="", max_length=80)
    email: str = Field(max_length=254)
    job_title: str = Field(default="", max_length=120)


class MembersIn(BaseModel):
    people: list[PersonIn] = Field(min_length=1, max_length=100)
    # Everyone listed gets this role; without it, the role a position names.
    role_id: uuid.UUID | None = None


class SkippedOut(BaseModel):
    email: str
    reason: str


class MembersAddedOut(BaseModel):
    created: list[MemberOut]
    skipped: list[SkippedOut]


class MemberPatch(BaseModel):
    """The fields to change; those left out stay as they are."""

    team_id: uuid.UUID | None = None
    # Sent as null, takes the role away; left out, keeps it.
    role_id: uuid.UUID | None = None
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    job_title: str | None = Field(default=None, max_length=120)


class MoveIn(BaseModel):
    """Several people to another team at once, as dragged there."""

    member_ids: list[uuid.UUID] = Field(min_length=1, max_length=300)
    team_id: uuid.UUID


class PatchIn(BaseModel):
    """One change and who gets it: the team, a role, or chosen people."""

    scope: Literal["team", "role", "people"]
    role_id: uuid.UUID | None = None
    member_ids: list[uuid.UUID] = Field(default=[], max_length=300)
    patch: ProfilePatch


class PatchOut(BaseModel):
    # Member profiles that changed now; those their readers made their own are left alone.
    changed: int


class MembershipOut(BaseModel):
    """Where the account stands in a company space."""

    company: str
    team: str | None
    role: Literal["owner", "member"]
    job_title: str | None = None
    # Who manages the space, as a member sees it.
    manager: str | None = None
    logo_url: str | None = None


class InviteOut(BaseModel):
    """What the invited person sees before setting a password."""

    display_name: str
    email: str
    company: str
    team: str
    job_title: str | None
    manager: str | None
    audience: Audience
    logo_url: str | None = None
    # The topics of the profile waiting in the account.
    interests: list[str]


class InviteAcceptIn(BaseModel):
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
