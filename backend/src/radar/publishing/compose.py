"""Writing a planned post: which story, in which words, with which picture."""

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy import ScalarResult, select
from sqlalchemy.ext.asyncio import AsyncSession

from radar.ai.factory import get_breaker, get_chat, get_embedder
from radar.cache import Cache
from radar.config import get_settings
from radar.db.models import Article, Profile, TelegramChannel, TelegramPost
from radar.domain import ProfileSpec
from radar.images.service import ensure_image_url
from radar.logging import get_logger
from radar.pipeline.sql_store import CachedQueryEmbedder
from radar.publishing.content import Button, Media, PostContent
from radar.publishing.markup import plain_text
from radar.publishing.settings import ChannelSettings
from radar.publishing.writer import (
    HeuristicPostWriter,
    NewsDraft,
    PostWriter,
    ResilientPostWriter,
    Story,
    Voice,
    render_digest,
    render_news,
)
from radar.selection.preview import build_preview

log = get_logger(__name__)

LIVE = ("composing", "draft", "queued", "sending", "sent")
SHRINK_STEPS = 6


class NothingToPost(Exception):
    """No story fits the slot: all were told already or none is relevant."""


@lru_cache
def get_post_writer() -> PostWriter:
    fallback = HeuristicPostWriter()
    chat = get_chat(temperature=get_settings().publish_temperature)
    if chat is None:
        return fallback

    from radar.publishing.writer import OllamaPostWriter

    return ResilientPostWriter(OllamaPostWriter(chat), fallback, get_breaker())


def channel_settings(channel: TelegramChannel) -> ChannelSettings:
    return ChannelSettings.model_validate(channel.settings or {})


def with_utm(url: str, utm: str) -> str:
    if not utm:
        return url
    parts = urlsplit(url)
    query = f"{parts.query}&{utm}" if parts.query else utm
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


async def told_here(session: AsyncSession, channel_id: uuid.UUID) -> set[int]:
    rows = await session.scalars(
        select(TelegramPost.article_ids).where(
            TelegramPost.channel_id == channel_id, TelegramPost.status.in_(LIVE)
        )
    )
    return {article_id for ids in rows for article_id in ids}


async def told_elsewhere(
    session: AsyncSession, channel: TelegramChannel, since: datetime
) -> set[int]:
    rows = await session.scalars(
        select(TelegramPost.article_ids).where(
            TelegramPost.user_id == channel.user_id,
            TelegramPost.channel_id != channel.id,
            TelegramPost.status.in_(LIVE),
            TelegramPost.created_at >= since,
        )
    )
    return {article_id for ids in rows for article_id in ids}


async def other_versions(
    session: AsyncSession, channel: TelegramChannel, article_id: int
) -> tuple[str, ...]:
    """How the owner's other channels already told this story."""
    rows: ScalarResult[dict[str, Any] | None] = await session.scalars(
        select(TelegramPost.content).where(
            TelegramPost.user_id == channel.user_id,
            TelegramPost.channel_id != channel.id,
            TelegramPost.article_ids.contains([article_id]),
            TelegramPost.status.in_(LIVE),
            TelegramPost.content.is_not(None),
        )
    )
    return tuple(plain_text(content.get("html", "")) for content in rows if content)


async def audience_profile(session: AsyncSession, channel: TelegramChannel) -> ProfileSpec | None:
    if channel.profile_id is None:
        return None
    profile = await session.get(Profile, channel.profile_id)
    if profile is None or profile.user_id != channel.user_id:
        return None
    return ProfileSpec.model_validate(profile.spec)


async def pick_articles(
    session: AsyncSession,
    *,
    channel: TelegramChannel,
    spec: ProfileSpec,
    cache: Cache,
    start: datetime,
    end: datetime,
    count: int,
    exclude: set[int],
    min_score: float,
) -> list[Article]:
    """The strongest stories of the window for the channel's audience."""
    settings = get_settings()
    embedder = get_embedder()
    preview = await build_preview(
        session,
        profile=spec,
        start=start,
        end=end,
        embedder=embedder,
        embed_queries=CachedQueryEmbedder(embedder, cache),
        per_interest_limit=settings.per_interest_limit,
        candidate_limit=settings.candidate_limit,
    )
    ranked = [
        graded.article.id
        for graded in preview.graded
        if graded.article.id in preview.selected_ids
        and graded.score >= min_score
        and graded.article.id not in exclude
    ][:count]
    if not ranked:
        return []
    rows = await session.scalars(select(Article).where(Article.id.in_(ranked)))
    by_id = {article.id: article for article in rows}
    return [by_id[article_id] for article_id in ranked if article_id in by_id]


def story_of(article: Article) -> Story:
    return Story(
        article_id=article.id,
        title=article.title,
        summary=article.summary,
        body=(article.content or "")[:4000],
        url=article.url,
        source=article.source.name,
        published_at=article.published_at,
        image_url=article.image_url,
    )


def voice_of(
    channel: TelegramChannel,
    settings: ChannelSettings,
    spec: ProfileSpec | None,
    others: tuple[str, ...],
) -> Voice:
    audience = settings.style.audience or (spec.role if spec else "") or (spec.name if spec else "")
    return Voice(
        channel=channel.title,
        username=channel.username,
        audience=audience,
        style=settings.style,
        links=settings.links,
        others=others,
    )


@dataclass(frozen=True, slots=True)
class Composed:
    content: PostContent
    article_ids: list[int]
    by_model: bool


async def compose_news(
    session: AsyncSession,
    channel: TelegramChannel,
    article: Article,
    settings: ChannelSettings,
    spec: ProfileSpec | None,
    client: httpx.AsyncClient,
) -> Composed:
    writer = get_post_writer()
    story = story_of(article)
    voice = voice_of(channel, settings, spec, await other_versions(session, channel, article.id))
    draft = await writer.news(story, voice)
    url = with_utm(article.url, settings.links.utm)

    media: tuple[Media, ...] = ()
    preview_url = None
    if settings.links.mode == "preview":
        # The card draws the article's own picture and title.
        preview_url = url
    elif settings.format.media == "auto":
        image = await ensure_image_url(article, client)
        if image:
            media = (Media(kind="photo", url=image),)
    buttons = (
        (Button(text=settings.links.button_text, url=url),)
        if settings.links.mode == "button"
        else ()
    )

    def build(current: NewsDraft) -> PostContent:
        return PostContent(
            format=settings.format.kind,
            html=render_news(current, voice, url),
            media=media,
            buttons=buttons,
            preview_url=preview_url,
            caption_above_media=settings.format.caption_above_media,
            silent=settings.format.silent,
            protect=settings.format.protect_content,
        )

    # Telegram refuses an over-long post: detail goes until it fits.
    content = build(draft)
    for _ in range(SHRINK_STEPS):
        if content.length() <= content.limit():
            break
        draft = _shorter(draft)
        content = build(draft)
    return Composed(content=content, article_ids=[article.id], by_model=draft.by_model)


def _shorter(draft: NewsDraft) -> NewsDraft:
    """One step less detail: bullets first, then the last paragraph, then the lead."""
    if draft.bullets:
        return replace(draft, bullets=draft.bullets[:-1])
    if len(draft.paragraphs) > 1:
        return replace(draft, paragraphs=draft.paragraphs[:-1])
    if draft.lead:
        return replace(draft, lead="")
    if draft.ending:
        return replace(draft, ending="")
    shorter = tuple(part[: len(part) * 2 // 3].rstrip() + "…" for part in draft.paragraphs)
    return replace(draft, paragraphs=shorter)


async def compose_digest(
    session: AsyncSession,
    channel: TelegramChannel,
    articles: list[Article],
    settings: ChannelSettings,
    spec: ProfileSpec | None,
    client: httpx.AsyncClient,
) -> Composed:
    writer = get_post_writer()
    stories = [story_of(article) for article in articles]
    voice = voice_of(channel, settings, spec, ())
    draft = await writer.digest(stories, voice)
    media: tuple[Media, ...] = ()
    if settings.format.media == "auto":
        for article in articles[:3]:
            image = await ensure_image_url(article, client)
            if image:
                media += (Media(kind="photo", url=image),)
        if settings.format.kind == "classic":
            media = media[:1]

    def build() -> PostContent:
        return PostContent(
            format=settings.format.kind,
            html=render_digest(draft, stories, voice),
            media=media,
            silent=settings.format.silent,
            protect=settings.format.protect_content,
        )

    content = build()
    while content.length() > content.limit() and len(stories) > 1:
        stories = stories[:-1]
        draft = replace(draft, items=draft.items[:-1])
        content = build()
    return Composed(
        content=content,
        article_ids=[story.article_id for story in stories],
        by_model=draft.by_model,
    )


def window(now: datetime, hours: int) -> tuple[datetime, datetime]:
    return now - timedelta(hours=hours), now


def utcnow() -> datetime:
    return datetime.now(UTC)
