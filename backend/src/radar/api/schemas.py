"""Request and response models of the HTTP API."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from radar.auth.passwords import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from radar.config import check_proxy_url
from radar.domain import (
    AddableSourceKind,
    ProfileSpec,
    ScheduleDefault,
    SourceCategory,
    SourceKind,
)
from radar.ingest.net import proxy_name
from radar.reader.blocks import Block
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


# How the feed looks: cards with the reasons in full, or posts as in a
# Telegram channel, with the article's picture.
FeedView = Literal["cards", "telegram"]
# Which order the feed opens in: the relevant articles newest first, or by score.
FeedOrder = Literal["new", "top"]


class MeOut(UserOut):
    # What the onboarding needs to know: is there anything to build a feed from.
    profiles: int
    resume_status: str | None
    # The reader's picture; the query string changes with every new one.
    avatar_url: str | None = None
    feed_view: FeedView = "cards"
    feed_order: FeedOrder = "new"


class SettingsIn(BaseModel):
    """The settings to change; those left out stay as they are."""

    feed_view: FeedView | None = None
    feed_order: FeedOrder | None = None


class SettingsOut(BaseModel):
    feed_view: FeedView
    feed_order: FeedOrder


class AvatarOut(BaseModel):
    avatar_url: str | None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    kind: SourceKind
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
    # The step of the fetch ladder that reads the source, and why not a lower one.
    fetch_method: str | None = None
    fetch_note: str | None = None
    fetch_changed_at: datetime | None = None
    fetch_via_proxy: bool = False
    # Polled again no sooner than this after a series of failures.
    retry_at: datetime | None = None
    robots_allowed: bool | None = None
    # The source's own proxy, its password hidden.
    proxy: str | None = Field(default=None, validation_alias="proxy_url")
    articles: int = 0
    articles_last_day: int = 0

    @field_validator("proxy")
    @classmethod
    def _hide_password(cls, url: str | None) -> str | None:
        return proxy_name(url) if url else None


class SourceCreate(BaseModel):
    kind: AddableSourceKind = "rss"
    # A channel may come without one: its own title is taken then.
    name: str | None = Field(default=None, min_length=2, max_length=200)
    feed_url: HttpUrl | None = None
    # A public Telegram channel: "@name" or its t.me address.
    channel: str | None = Field(default=None, max_length=200)
    site_url: HttpUrl | None = None
    category: SourceCategory
    language: Literal["ru", "en"] = "ru"
    fetch_full_text: bool = False
    # A proxy for this source only: http://, https:// or socks5://.
    proxy_url: str | None = Field(default=None, max_length=500)

    @field_validator("proxy_url")
    @classmethod
    def _proxy(cls, url: str | None) -> str | None:
        return proxy_or_none(url)

    @model_validator(mode="after")
    def _address(self) -> SourceCreate:
        if self.kind == "rss" and (
            self.feed_url is None or self.name is None or self.channel is not None
        ):
            raise ValueError("a feed takes a name and feed_url, and no channel")
        if self.kind == "telegram" and (self.channel is None or self.feed_url is not None):
            raise ValueError("a Telegram source takes a channel, and no feed_url")
        return self


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    category: SourceCategory | None = None
    enabled: bool | None = None
    fetch_full_text: bool | None = None
    # An empty string takes the source's proxy away.
    proxy_url: str | None = Field(default=None, max_length=500)

    @field_validator("proxy_url")
    @classmethod
    def _proxy(cls, url: str | None) -> str | None:
        return proxy_or_none(url)


def proxy_or_none(url: str | None) -> str | None:
    """A proxy address checked, or None for an empty one."""
    return check_proxy_url(url.strip()) if url and url.strip() else None


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
    # In a search: found by the words of the query, or only by its meaning.
    match: Literal["words", "meaning"] | None = None


class ArticleReadOut(BaseModel):
    """An article opened in the app: its text as blocks, pictures named in them."""

    id: int
    url: str
    title: str
    author: str | None
    source_id: int
    source_name: str
    source_category: str
    language: str
    tags: list[str]
    published_at: datetime
    reading_minutes: int | None
    # The whole text, or only what the feed carried when the page could not be read.
    complete: bool
    blocks: list[Annotated[Block, Field(discriminator="type")]]


class ProfileDefaults(BaseModel):
    """What the profile's audience suggests: the period of a digest and a
    schedule. The web app and the console start from these."""

    period_days: int
    schedule: ScheduleDefault


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
    defaults: ProfileDefaults
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
    # Neither days nor bounds: the period of the profile's audience.
    period_days: int | None = Field(default=None, ge=1, le=90)
    period_start: datetime | None = None
    period_end: datetime | None = None

    @model_validator(mode="after")
    def _period(self) -> DigestCreate:
        explicit = self.period_start is not None and self.period_end is not None
        if explicit and self.period_start >= self.period_end:  # type: ignore[operator]
            raise ValueError("period_start must be before period_end")
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
    # False: the app enters a visitor as a guest instead of showing sign-in.
    sign_in_required: bool = True
    resume_parser: str
    resume_formats: list[str]
    resume_max_bytes: int
    # Short videos of digests can be ordered, and whether they get a voice.
    shorts: bool = False
    shorts_voice: bool = False
    # Voices a reader can pick; empty when the voice service offers no choice.
    short_voices: list[VoiceOption] = []
