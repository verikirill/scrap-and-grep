"""Read models of a digest, shared by the API and the renderers."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from radar.db.models import Digest, DigestItem
from radar.domain import ProfileSpec


class DuplicateView(BaseModel):
    title: str
    url: str
    source_name: str


class ItemView(BaseModel):
    article_id: int
    url: str
    title: str
    headline: str
    source_name: str
    source_category: str
    language: str
    published_at: datetime
    score: float
    retrieval_score: float
    relevance: int
    interest_id: str | None
    interest_title: str | None
    reason: str
    summary: str
    why: str
    duplicates: list[DuplicateView] = []
    reject_reason: str | None = None


class TopicView(BaseModel):
    title: str
    overview: str
    items: list[ItemView]


class DigestSummaryView(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID | None
    profile_name: str
    profile_version: int
    period_start: datetime
    period_end: datetime
    status: str
    stage: str | None
    progress: float
    error: str | None
    title: str | None
    stats: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None


class DigestView(DigestSummaryView):
    profile: ProfileSpec
    highlights: list[str]
    topics: list[TopicView]
    rejected: list[ItemView]


def _item_view(item: DigestItem, profile: ProfileSpec) -> ItemView:
    article = item.article
    interest = profile.interest(item.interest_id)
    return ItemView(
        article_id=article.id,
        url=article.url,
        title=article.title,
        headline=item.headline or article.title,
        source_name=article.source.name,
        source_category=article.source.category,
        language=article.language,
        published_at=article.published_at,
        score=round(item.score, 3),
        retrieval_score=round(item.retrieval_score, 3),
        relevance=item.relevance,
        interest_id=item.interest_id,
        interest_title=interest.title if interest else None,
        reason=item.reason,
        summary=item.summary,
        why=item.why,
        duplicates=[DuplicateView.model_validate(dup) for dup in item.duplicates],
        reject_reason=item.reject_reason,
    )


def digest_summary(digest: Digest) -> DigestSummaryView:
    return DigestSummaryView(
        id=digest.id,
        profile_id=digest.profile_id,
        profile_name=digest.profile_spec.get("name", ""),
        profile_version=digest.profile_version,
        period_start=digest.period_start,
        period_end=digest.period_end,
        status=digest.status,
        stage=digest.stage,
        progress=digest.progress,
        error=digest.error,
        title=digest.title,
        stats=digest.stats,
        created_at=digest.created_at,
        finished_at=digest.finished_at,
    )


def digest_view(digest: Digest) -> DigestView:
    """Build the full view; `digest` must be loaded with topics and items."""
    profile = ProfileSpec.model_validate(digest.profile_spec)
    by_topic: dict[int, list[ItemView]] = {}
    rejected = []
    for item in digest.items:
        view = _item_view(item, profile)
        if item.selected and item.topic_id is not None:
            by_topic.setdefault(item.topic_id, []).append(view)
        else:
            rejected.append(view)
    return DigestView(
        **digest_summary(digest).model_dump(),
        profile=profile,
        highlights=list(digest.highlights),
        topics=[
            TopicView(title=topic.title, overview=topic.overview, items=by_topic.get(topic.id, []))
            for topic in digest.topics
        ],
        rejected=sorted(rejected, key=lambda view: -view.score),
    )
