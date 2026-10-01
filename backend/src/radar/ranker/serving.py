"""Which ranker a reader gets, and the learned one's scores."""

import uuid
from dataclasses import dataclass

VARIANT_HAND = "hand"
VARIANT_LEARNED = "learned"


@dataclass(frozen=True, slots=True)
class Assignment:
    variant: str
    model_version: str = ""


async def assignment(user_id: uuid.UUID) -> Assignment:
    """The reader's arm of the comparison."""
    return Assignment(VARIANT_HAND)
