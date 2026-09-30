"""Domain objects passed between ingestion, selection, the pipeline and rendering.

They are plain pydantic models with no database or framework knowledge, so the
selection logic can be tested without infrastructure.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from radar.text import stable_hash

SourceCategory = Literal["security", "ics", "it", "energy", "regulator"]
Language = Literal["ru", "en"]


class Interest(BaseModel):
    """One thing the reader cares about."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=600)
    keywords: tuple[str, ...] = ()
    weight: float = Field(default=1.0, ge=0.5, le=1.5)

    @field_validator("keywords", mode="before")
    @classmethod
    def _clean_keywords(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            cleaned = [str(item).strip()[:80] for item in value if str(item).strip()]
            return tuple(dict.fromkeys(cleaned))[:30]
        return value

    def as_query(self) -> str:
        """Text that represents the interest in embedding space."""
        parts = [self.title, self.description, ", ".join(self.keywords)]
        return ". ".join(part for part in parts if part)


class ProfileSpec(BaseModel):
    """Everything about a reader that influences selection."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=2, max_length=120)
    role: str = Field(default="", max_length=600)
    interests: tuple[Interest, ...] = Field(min_length=1, max_length=20)
    exclusions: tuple[str, ...] = Field(default=(), max_length=20)
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)
    max_items: int = Field(default=20, ge=3, le=60)
    languages: tuple[Language, ...] = Field(default=("ru", "en"), min_length=1, max_length=2)
    categories: tuple[SourceCategory, ...] = Field(default=(), max_length=5)

    @field_validator("interests")
    @classmethod
    def _unique_ids(cls, value: tuple[Interest, ...]) -> tuple[Interest, ...]:
        ids = [interest.id for interest in value]
        if len(set(ids)) != len(ids):
            raise ValueError("interest ids must be unique")
        return value

    @field_validator("exclusions", mode="before")
    @classmethod
    def _clean_exclusions(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            cleaned = [str(item).strip()[:120] for item in value if str(item).strip()]
            return tuple(dict.fromkeys(cleaned))
        return value

    def fingerprint(self) -> str:
        """Changes whenever anything that affects grading changes."""
        return stable_hash(self.model_dump_json(exclude={"name", "max_items", "min_score"}))

    def interest(self, interest_id: str | None) -> Interest | None:
        return next((item for item in self.interests if item.id == interest_id), None)


class ArticleRef(BaseModel):
    """The slice of an article the pipeline needs."""

    id: int
    url: str
    title: str
    summary: str
    content: str | None = None
    source_name: str
    source_category: str
    language: str
    published_at: datetime
    content_hash: str

    def body(self, limit: int) -> str:
        return (self.content or self.summary or "")[:limit]


class Candidate(BaseModel):
    """An article retrieved for a profile, before any judgement."""

    article: ArticleRef
    interest_id: str
    similarity: float = 0.0
    z_score: float = 0.0
    lexical_hit: bool = False
    retrieval_score: float = 0.0
    excluded_by: str | None = None


class Grade(BaseModel):
    """Relevance verdict for one candidate.

    `by_model` is False when the verdict came from the offline heuristic,
    either by configuration or because the model server was unavailable.
    """

    relevance: int = Field(ge=0, le=3)
    interest_id: str | None = None
    reason: str = ""
    by_model: bool = False


class GradedCandidate(BaseModel):
    candidate: Candidate
    grade: Grade
    score: float

    @property
    def article(self) -> ArticleRef:
        return self.candidate.article

    @property
    def interest_id(self) -> str:
        return self.grade.interest_id or self.candidate.interest_id


class DuplicateRef(BaseModel):
    title: str
    url: str
    source_name: str


class ItemSummary(BaseModel):
    headline: str = ""
    summary: str
    why: str = ""
    by_model: bool = False


class SelectedItem(BaseModel):
    graded: GradedCandidate
    duplicates: tuple[DuplicateRef, ...] = ()
    text: ItemSummary | None = None

    @property
    def article(self) -> ArticleRef:
        return self.graded.candidate.article


class TopicName(BaseModel):
    title: str
    overview: str = ""
    by_model: bool = False


class DigestOverview(BaseModel):
    title: str
    highlights: tuple[str, ...] = ()
    by_model: bool = False


class Topic(BaseModel):
    title: str
    overview: str = ""
    items: tuple[SelectedItem, ...]
