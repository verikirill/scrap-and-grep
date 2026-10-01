"""Request and response models of the HTTP API."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from radar.auth.passwords import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from radar.domain import ProfileSpec, SourceCategory
from radar.shorts.voice import VoiceOption
from radar.views import ItemView


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class RegisterIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    display_name: str = Field(min_length=2, max_length=80)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class PasswordIn(BaseModel):
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool
    is_demo: bool


class MeOut(UserOut):
    # What the onboarding needs to know: is there anything to build a feed from.
    profiles: int
    resume_status: str | None
    # The reader's picture; the query string changes with every new one.
    avatar_url: str | None = None


class AvatarOut(BaseModel):
    avatar_url: str | None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    feed_url: str
    site_url: str | None
    category: str
    language: str
    enabled: bool
    fetch_full_text: bool
    last_fetched_at: datetime | None
    last_status: str | None
    last_error: str | None
    consecutive_failures: int
    articles: int = 0
    articles_last_day: int = 0


class SourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    feed_url: HttpUrl
    site_url: HttpUrl | None = None
    category: SourceCategory
    language: Literal["ru", "en"] = "ru"
    fetch_full_text: bool = False


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    category: SourceCategory | None = None
    enabled: bool | None = None
    fetch_full_text: bool | None = None


class ArticleOut(BaseModel):
    id: int
    url: str
    title: str
    summary: str
    has_full_text: bool
    source_id: int
    source_name: str
    source_category: str
    language: str
    tags: list[str]
    published_at: datetime


class ProfileOut(BaseModel):
    id: uuid.UUID
    version: int
    spec: ProfileSpec
    icon: str | None = None
    color: str | None = None
    # Only the owner lists their profiles, so only the owner sees the link.
    share_token: str | None = None
    # Whether the profile follows its reader's marks.
    adaptive: bool = True
    created_at: datetime
    updated_at: datetime


class ProfileLook(BaseModel):
    """A profile's icon and colour: keys of the sets the web app draws, or a
    colour of the reader's own as #rrggbb."""

    icon: str | None = Field(default=None, pattern=r"^[a-z][a-z_]{1,23}$")
    color: str | None = Field(default=None, pattern=r"^(?:[a-z]{3,12}|#[0-9a-fA-F]{6})$")

    @field_validator("color")
    @classmethod
    def _lower(cls, value: str | None) -> str | None:
        return value.lower() if value else value


class SharedProfileOut(BaseModel):
    """A profile someone sent by link, as the reader who opened it sees it."""

    spec: ProfileSpec
    icon: str | None
    color: str | None
    # The reader's own profile with the same content: the owner's original,
    # or a copy added from this link before.
    own_id: uuid.UUID | None


class DigestCreate(BaseModel):
    profile_id: uuid.UUID
    period_days: int | None = Field(default=7, ge=1, le=90)
    period_start: datetime | None = None
    period_end: datetime | None = None

    @model_validator(mode="after")
    def _period(self) -> DigestCreate:
        explicit = self.period_start is not None and self.period_end is not None
        if explicit and self.period_start >= self.period_end:  # type: ignore[operator]
            raise ValueError("period_start must be before period_end")
        if not explicit and self.period_days is None:
            raise ValueError("either period_days or both period bounds are required")
        return self


class PreviewRequest(BaseModel):
    profile: ProfileSpec
    period_days: int = Field(default=7, ge=1, le=90)


class PreviewItem(BaseModel):
    article_id: int
    url: str
    title: str
    source_name: str
    published_at: datetime
    score: float
    interest_id: str
    interest_title: str | None
    lexical_hit: bool
    selected: bool
    reject_reason: str | None


class PreviewOut(BaseModel):
    window_total: int
    candidates: int
    selected: int
    lexical_only: bool
    embedding_model: str
    items: list[PreviewItem]


class ScoreChange(BaseModel):
    item: ItemView
    base_score: float
    delta: float


class InterestChange(BaseModel):
    id: str
    title: str
    change: Literal["added", "removed", "changed"]


class CompareOut(BaseModel):
    base_id: uuid.UUID
    other_id: uuid.UUID
    added: list[ItemView]
    removed: list[ItemView]
    kept: list[ScoreChange]
    interest_changes: list[InterestChange]
    settings_changed: list[str]


class MetaOut(BaseModel):
    version: str
    embedding_provider: str
    embedding_model: str
    llm_provider: str
    llm_model: str
    articles: int
    articles_last_day: int
    embedded: int
    oldest_article: datetime | None
    newest_article: datetime | None
    sources: int
    sources_failing: int
    demo_login: bool
    registration_open: bool
    resume_parser: str
    resume_formats: list[str]
    resume_max_bytes: int
    # Short videos of digests can be ordered, and whether they get a voice.
    shorts: bool = False
    shorts_voice: bool = False
    # Voices a reader can pick; empty when the voice service offers no choice.
    short_voices: list[VoiceOption] = []
