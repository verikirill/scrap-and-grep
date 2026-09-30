"""What is known about a reader from their resume."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

STATUS_PROCESSING = "processing"
STATUS_READY = "ready"
STATUS_FAILED = "failed"

Seniority = Literal["junior", "middle", "senior", "lead", "executive", "unknown"]


class ResumeError(Exception):
    """The file cannot be used. The message is written for the reader."""


class ResumeFacts(BaseModel):
    """Professional facts, without anything that identifies the person."""

    model_config = ConfigDict(frozen=True)

    headline: str = Field(max_length=120)
    seniority: Seniority = "unknown"
    summary: str = Field(default="", max_length=600)
    skills: tuple[str, ...] = Field(default=(), max_length=40)
    domains: tuple[str, ...] = Field(default=(), max_length=10)
    # False when the offline taxonomy produced the facts.
    by_model: bool = False

    @field_validator("skills", "domains", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            cleaned = [str(item).strip()[:60] for item in value if str(item).strip()]
            return tuple(dict.fromkeys(cleaned))
        return value

    def as_query(self) -> str:
        """Text that stands for the reader's background in embedding space."""
        parts = [self.headline, ", ".join(self.domains), ", ".join(self.skills), self.summary]
        return ". ".join(part for part in parts if part)
