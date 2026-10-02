"""Read models of a digest, shared by the API and the renderers."""

import uuid
from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, model_validator

from radar.cards import TAG_LABELS, attack_rows, priority_reason, reference_rows, vulnerability_rows
from radar.db.models import Digest, DigestItem
from radar.domain import (
    AttackCard,
    ItemSummary,
    ManagementTag,
    Priority,
    ProfileSpec,
    RecordKind,
    VulnerabilityCard,
    VulnerabilityReference,
)
from radar.reading import reading_minutes


class DuplicateView(BaseModel):
    title: str
    url: str
    source_name: str


class CardField(BaseModel):
    label: str
    value: str


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
    personal: float = 0.0
    personal_note: str = ""
    relevance: int
    interest_id: str | None
    interest_title: str | None
    reason: str
    summary: str
    why: str
    duplicates: list[DuplicateView] = []
    reject_reason: str | None = None
    reading_minutes: int | None = None
    # The organizers' dataset: what the publication reports, its priority and card.
    kind: RecordKind = "news"
    priority: Priority | None = None
    priority_reason: str = ""
    attack: AttackCard | None = None
    vulnerability: VulnerabilityCard | None = None
    tags: list[ManagementTag] = []
    # What the check against the article's text took out of the entry.
    unsupported: list[str] = []
    # Addresses a Telegram post cites.
    links: list[str] = []
    # The bases the card was checked against.
    references: list[VulnerabilityReference] = []
    # The card as label and value, in the dataset's order, and the tags in
    # words: worked out from the fields above, for the page and the exports.
    fields: list[CardField] = []
    tag_labels: list[str] = []

    @model_validator(mode="after")
    def _derived(self) -> Self:
        rows: list[tuple[str, str]] = []
        if self.attack is not None:
            rows = attack_rows(self.attack) + reference_rows(self.references)
        elif self.vulnerability is not None:
            rows = vulnerability_rows(self.vulnerability) + reference_rows(self.references)
        self.fields = [CardField(label=label, value=value) for label, value in rows]
        self.tag_labels = [TAG_LABELS[tag] for tag in self.tags]
        return self


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
    # "schedule" for a digest the reader's schedule ordered.
    origin: str = "manual"
    created_at: datetime
    finished_at: datetime | None


class DigestView(DigestSummaryView):
    profile: ProfileSpec
    highlights: list[str]
    # Management only: what the period means for the company.
    implications: list[str] = []
    topics: list[TopicView]
    rejected: list[ItemView]


# Stored as plain strings; read back as the values the domain knows.
_KINDS: dict[str, RecordKind] = {"attack": "attack", "vulnerability": "vulnerability"}
_PRIORITIES: dict[str, Priority] = {"high": "high", "medium": "medium", "low": "low"}


def _item_view(item: DigestItem, profile: ProfileSpec) -> ItemView:
    article = item.article
    interest = profile.interest(item.interest_id)
    card = ItemSummary.model_validate({"summary": item.summary, **(item.card or {})})
    kind = _KINDS.get(item.kind, "news")
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
        personal=round(item.personal, 3),
        personal_note=item.personal_note,
        relevance=item.relevance,
        interest_id=item.interest_id,
        interest_title=interest.title if interest else None,
        reason=item.reason,
        summary=item.summary,
        why=item.why,
        duplicates=[DuplicateView.model_validate(dup) for dup in item.duplicates],
        reject_reason=item.reject_reason,
        reading_minutes=reading_minutes(article.word_count, article.language),
        kind=kind,
        priority=_PRIORITIES.get(item.priority or ""),
        priority_reason=priority_reason(kind, card) if item.priority else "",
        attack=card.attack,
        vulnerability=card.vulnerability,
        tags=list(card.tags),
        unsupported=list(card.unsupported),
        links=list(article.links or []),
        references=list(card.references),
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
        origin=digest.origin,
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
        implications=list(digest.implications),
        topics=[
            TopicView(title=topic.title, overview=topic.overview, items=by_topic.get(topic.id, []))
            for topic in digest.topics
        ],
        rejected=sorted(rejected, key=lambda view: -view.score),
    )
