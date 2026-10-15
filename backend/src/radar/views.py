"""Read models of a digest, shared by the API and the renderers."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from radar.cards import (
    OTHER_TOPIC,
    TAG_LABELS,
    card_fields,
    plain_brief,
    plain_lines,
    plain_prose,
    plain_title,
    priority_reason,
)
from radar.db.models import Digest, DigestItem
from radar.digest_extras import (
    Change,
    ManualWork,
    PlanEntry,
    TagCount,
    manual_work,
    numbers_title,
    period_numbers,
    shift_plan,
    stored_changes,
)
from radar.domain import (
    AttackCard,
    Audience,
    CardFieldKey,
    ItemSummary,
    ManagementTag,
    Priority,
    ProfileSpec,
    RecordKind,
    VulnerabilityCard,
    VulnerabilityReference,
)
from radar.reading import reading_minutes
from radar.systems import affected_systems, entry_text


class DuplicateView(BaseModel):
    title: str
    url: str
    source_name: str


class CardField(BaseModel):
    key: CardFieldKey
    label: str
    value: str


class ItemView(BaseModel):
    article_id: int
    url: str
    title: str
    headline: str
    source_name: str
    source_category: str
    # How the source gets past a site that refuses a bot; empty for a plain read.
    source_read_via: str = ""
    # The reader's own systems the entry names.
    ours: list[str] = []
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
    # The card rows the reader chose not to see (ProfileSpec.hidden_card_fields).
    hidden_fields: list[CardFieldKey] = []
    # The card as label and value, in the dataset's order and without the
    # hidden rows, and the tags in words: worked out from the fields above,
    # for the page and the exports.
    fields: list[CardField] = []
    tag_labels: list[str] = []

    @field_validator("fields", mode="before")
    @classmethod
    def _worked_out_again(cls, value: object) -> object:
        """Rows a saved view holds, written before rows had keys, are not read:
        they are worked out again from the card below."""
        return []

    @model_validator(mode="after")
    def _derived(self) -> Self:
        rows = card_fields(self.attack, self.vulnerability, self.references, self.hidden_fields)
        self.fields = [CardField(key=key, label=label, value=value) for key, label, value in rows]
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
    # Who the digest was written for; for both audiences of one profile the
    # two digests differ in this alone.
    audience: Audience = "specialist"
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
    # Worked out from the entries, never by the model (radar.digest_extras):
    # the handwork the issue spares; for a specialist the plan for the shift and
    # what changed since earlier issues; for management the period in numbers.
    manual: ManualWork | None = None
    plan: list[PlanEntry] = []
    changes: list[Change] = []
    numbers: list[TagCount] = []
    numbers_title: str = ""
    # The card rows left out of every entry, as the reader set them.
    hidden_card_fields: list[CardFieldKey] = []
    # The addresses of the plan's lines the reader ticked off; shown as each
    # line's `done`, not sent on their own.
    plan_done: list[str] = Field(default=[], exclude=True)

    @model_validator(mode="after")
    def _extras(self) -> Self:
        selected = [item for topic in self.topics for item in topic.items]
        self.manual = manual_work(self.stats, self.profile.audience)
        if self.profile.audience == "management":
            before = self.stats.get("tags_before")
            self.numbers = period_numbers(selected, before if isinstance(before, dict) else None)
            self.numbers_title = numbers_title(self.period_start, self.period_end)
        else:
            self.plan = shift_plan(selected, set(self.plan_done))
            self.changes = stored_changes(self.stats.get("changes"))
        return self


# The fetch ladder's steps above a plain request, as an entry names them.
READ_VIA_LABELS = {
    "browser_headers": "заголовки браузера",
    "impersonate": "отпечаток Chrome",
    "browser": "браузер",
    "solver": "FlareSolverr",
}


def read_via(fetch_method: str | None, via_proxy: bool) -> str:
    """How the entry's source is read when a plain request is refused:
    "браузер", "отпечаток Chrome, через прокси"; empty for a plain read."""
    parts = [READ_VIA_LABELS[fetch_method]] if fetch_method in READ_VIA_LABELS else []
    if via_proxy:
        parts.append("через прокси")
    return ", ".join(parts)


# Stored as plain strings; read back as the values the domain knows.
_KINDS: dict[str, RecordKind] = {"attack": "attack", "vulnerability": "vulnerability"}
_PRIORITIES: dict[str, Priority] = {"high": "high", "medium": "medium", "low": "low"}


def _item_view(item: DigestItem, profile: ProfileSpec, hidden: Sequence[CardFieldKey]) -> ItemView:
    article = item.article
    interest = profile.interest(item.interest_id)
    card = ItemSummary.model_validate({"summary": item.summary, **(item.card or {})})
    kind = _KINDS.get(item.kind, "news")
    text = ItemSummary(headline=item.headline, summary=item.summary, why=item.why)
    title, reason = article.title, item.reason
    if profile.audience == "management":
        # An issue saved before the rules reads by them too; the source's own
        # title and the grade's reason show under a headline and in what was
        # left out, so they lose ids, scores and versions as well.
        text = plain_brief(text)
        title, reason = plain_title(title), plain_title(reason)
    return ItemView(
        article_id=article.id,
        url=article.url,
        title=title,
        headline=text.headline or title,
        source_name=article.source.name,
        source_category=article.source.category,
        source_read_via=read_via(article.source.fetch_method, article.source.fetch_via_proxy),
        ours=list(
            affected_systems(
                profile.systems,
                entry_text(item.headline or article.title, article.title, item.summary, card),
            )
        ),
        language=article.language,
        published_at=article.published_at,
        score=round(item.score, 3),
        retrieval_score=round(item.retrieval_score, 3),
        personal=round(item.personal, 3),
        personal_note=item.personal_note,
        relevance=item.relevance,
        interest_id=item.interest_id,
        interest_title=interest.title if interest else None,
        reason=reason,
        summary=text.summary,
        why=text.why,
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
        hidden_fields=list(hidden),
    )


def digest_summary(digest: Digest) -> DigestSummaryView:
    return DigestSummaryView(
        id=digest.id,
        profile_id=digest.profile_id,
        profile_name=digest.profile_spec.get("name", ""),
        profile_version=digest.profile_version,
        audience=digest.profile_spec.get("audience", "specialist"),
        period_start=digest.period_start,
        period_end=digest.period_end,
        status=digest.status,
        stage=digest.stage,
        progress=digest.progress,
        error=digest.error,
        # An issue for management saved before the rules may name a CVE here.
        title=(
            plain_title(digest.title) or None
            if digest.title and digest.profile_spec.get("audience") == "management"
            else digest.title
        ),
        stats=digest.stats,
        origin=digest.origin,
        created_at=digest.created_at,
        finished_at=digest.finished_at,
    )


def digest_view(digest: Digest, hidden: Sequence[CardFieldKey] | None = None) -> DigestView:
    """Build the full view; `digest` must be loaded with topics and items.

    `hidden` are the card rows to leave out, as the reader's profile has them
    now; without it the profile the issue was built for decides."""
    profile = ProfileSpec.model_validate(digest.profile_spec)
    if hidden is None:
        hidden = profile.hidden_card_fields
    management = profile.audience == "management"
    by_topic: dict[int, list[ItemView]] = {}
    rejected = []
    for item in digest.items:
        view = _item_view(item, profile, hidden)
        if item.selected and item.topic_id is not None:
            by_topic.setdefault(item.topic_id, []).append(view)
        else:
            rejected.append(view)
    for views in by_topic.values():
        # What names the reader's own systems first; the sort keeps the order
        # within both groups.
        views.sort(key=lambda view: not view.ours)
    highlights, implications = list(digest.highlights), list(digest.implications)
    if management:
        highlights = list(plain_lines(highlights, len(highlights)))
        implications = list(plain_lines(implications, len(implications)))
    return DigestView(
        **digest_summary(digest).model_dump(),
        profile=profile,
        highlights=highlights,
        implications=implications,
        topics=[
            TopicView(
                title=(plain_title(topic.title) or OTHER_TOPIC) if management else topic.title,
                overview=plain_prose(topic.overview) if management else topic.overview,
                items=by_topic.get(topic.id, []),
            )
            for topic in digest.topics
        ],
        rejected=sorted(rejected, key=lambda view: -view.score),
        hidden_card_fields=list(hidden),
        plan_done=list(digest.plan_done or []),
    )
