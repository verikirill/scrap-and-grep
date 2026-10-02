"""Domain objects passed between ingestion, selection, the pipeline and rendering.

They are plain pydantic models with no database or framework knowledge, so the
selection logic can be tested without infrastructure.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from radar.text import stable_hash

SourceCategory = Literal["security", "ics", "it", "energy", "regulator"]
# An RSS or Atom feed, a public Telegram channel, the trending
# vulnerabilities page of Positive Technologies, the REST API of a WordPress
# site, or a news page without a feed.
SourceKind = Literal["rss", "telegram", "pt_trending", "wordpress", "page"]
# What can be added; the PT page comes with the defaults.
AddableSourceKind = Literal["rss", "telegram", "wordpress", "page"]
Language = Literal["ru", "en"]
# Who reads the digest, as in the organizers' dataset: specialists get a card
# per attack and vulnerability, management a short brief with tags.
Audience = Literal["specialist", "management"]

# How often each audience reads, as the jury put it: specialists every day,
# management less often. The period of a digest built without one and the
# schedule a profile is offered follow it; nothing is scheduled by itself.
AUDIENCE_PERIOD_DAYS: dict[Audience, int] = {"specialist": 1, "management": 7}


class ScheduleDefault(BaseModel):
    """A schedule as the reader is offered it, in their local time."""

    model_config = ConfigDict(frozen=True)

    cadence: Literal["daily", "weekdays", "weekly"]
    # Monday is 0; for a weekly schedule only.
    weekday: int | None = None
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


AUDIENCE_SCHEDULE: dict[Audience, ScheduleDefault] = {
    "specialist": ScheduleDefault(cadence="weekdays", time="08:30"),
    "management": ScheduleDefault(cadence="weekly", weekday=0, time="09:00"),
}

# What a publication reports, the dataset's grouping for specialists.
RecordKind = Literal["attack", "vulnerability", "news"]
Priority = Literal["high", "medium", "low"]
# in_the_wild: used in attacks; public: a proof of concept is out.
Exploit = Literal["in_the_wild", "public", "none", "unknown"]
# The dataset's grouping features for management, in its order.
ManagementTag = Literal[
    "ru",
    "abroad",
    "financial_loss",
    "critical_infrastructure",
    "energy",
    "industry",
    "reputation",
    "data_leak",
    "government_law",
    "mass_service",
    "people_events",
    "curious",
]


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
    audience: Audience = "specialist"

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
        # The audience changes how an entry is written, not how it is graded.
        return stable_hash(
            self.model_dump_json(exclude={"name", "max_items", "min_score", "audience"})
        )

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
    # Addresses a Telegram post points to, besides the post itself.
    links: tuple[str, ...] = ()

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
    kind: RecordKind = "news"
    by_model: bool = False


class GradedCandidate(BaseModel):
    candidate: Candidate
    grade: Grade
    score: float
    # What the reader's own behaviour added to or took from the score.
    personal: float = 0.0
    personal_note: str = ""
    # The reader disliked or hid this very article.
    rejected_by_reader: bool = False

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


class AttackTechnique(BaseModel):
    """A technique of MITRE ATT&CK: T1566, or a sub-technique T1566.001."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^T\d{4}(?:\.\d{3})?$")
    name: str = ""


class AttackCard(BaseModel):
    """The dataset's card of an attack. Empty means the text does not say."""

    victim_country: str = ""
    victim_in_russia: bool | None = None
    group: str = ""
    attack_date: str = ""
    sectors: str = ""
    energy_sector: bool | None = None
    # The way in, broadly (phishing, a flaw on the perimeter, a contractor),
    # and the concrete entry point.
    vector: str = ""
    initial_access: str = ""
    # Products and versions the attack went through.
    affected: str = ""
    tools: tuple[str, ...] = ()
    vulnerabilities: tuple[str, ...] = ()
    techniques: tuple[AttackTechnique, ...] = ()
    iocs: bool | None = None
    # Addresses, domains and hashes from the text, defanged.
    indicators: tuple[str, ...] = ()


class VulnerabilityCard(BaseModel):
    """The dataset's card of a vulnerability; the entry's summary describes it."""

    name: str = ""
    affected: str = ""
    fix: str = ""
    workaround: str = ""
    exploit: Exploit = "unknown"
    ids: tuple[str, ...] = ()
    cvss_score: str = ""
    cvss_vector: str = ""
    impact: str = ""
    cwe: tuple[str, ...] = ()
    # For industrial control systems: the maker and model of the equipment,
    # and the protocols it speaks.
    equipment: str = ""
    protocols: str = ""


class VulnerabilityReference(BaseModel):
    """What the reference bases say of one vulnerability: the CISA catalogue of
    exploited vulnerabilities and the BDU of FSTEC of Russia."""

    id: str
    kev_added: date | None = None
    kev_ransomware: bool = False
    # The date CISA wants it fixed by, and the weaknesses it names.
    kev_due: date | None = None
    kev_cwes: tuple[str, ...] = ()
    bdu_id: str = ""
    bdu_exploit: str = ""
    bdu_in_attacks: bool = False
    bdu_cvss: str = ""
    bdu_vector: str = ""
    bdu_fix: str = ""
    # "model" when the model asked for it with its tool, "pipeline" when the
    # digest looked it up for an id on the card the model did not ask about.
    via: str = "pipeline"

    @property
    def found(self) -> bool:
        return self.kev_added is not None or bool(self.bdu_id)

    def text(self) -> str:
        """The facts in words, for the model and for the check of a card."""
        parts = []
        if self.kev_added is not None:
            ransomware = ", в том числе вымогателями" if self.kev_ransomware else ""
            added = f"{self.kev_added:%d.%m.%Y}"
            kev = f"в каталоге CISA KEV с {added}: используется в атаках{ransomware}"
            if self.kev_due is not None:
                kev += f", устранить до {self.kev_due:%d.%m.%Y}"
            if self.kev_cwes:
                kev += f", {', '.join(self.kev_cwes)}"
            parts.append(kev)
        if self.bdu_id:
            bdu = [self.bdu_id]
            if self.bdu_exploit:
                bdu.append(f"эксплойт: {self.bdu_exploit}")
            if self.bdu_in_attacks:
                bdu.append("используется в атаках")
            if self.bdu_cvss:
                bdu.append(f"оценка CVSS {self.bdu_cvss}")
            if self.bdu_vector:
                bdu.append(f"вектор {self.bdu_vector}")
            if self.bdu_fix:
                bdu.append(f"устранение: {self.bdu_fix}")
            parts.append("БДУ ФСТЭК " + ", ".join(bdu))
        return f"{self.id}: " + ("; ".join(parts) if parts else "нет в CISA KEV и БДУ ФСТЭК")


class ItemSummary(BaseModel):
    headline: str = ""
    summary: str
    why: str = ""
    by_model: bool = False
    attack: AttackCard | None = None
    vulnerability: VulnerabilityCard | None = None
    tags: tuple[ManagementTag, ...] = ()
    # Card fields and claims the check against the article's text took out.
    unsupported: tuple[str, ...] = ()
    # The bases the card was checked against, id by id.
    references: tuple[VulnerabilityReference, ...] = ()


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
    # Management only: what the period means for the company, two or three points.
    implications: tuple[str, ...] = ()
    by_model: bool = False


class Topic(BaseModel):
    title: str
    overview: str = ""
    items: tuple[SelectedItem, ...]
