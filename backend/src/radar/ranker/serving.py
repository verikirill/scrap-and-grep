"""Which ranker a reader gets, and the learned one's order.

While a model is switched on, readers are split by a hash of their id: a
share of them (RADAR_RANKER_SHARE) gets the model, the rest stays on the
hand blend as the control group. Each reader keeps their side. Without a
model everyone is on the hand blend, labelled apart from the control group,
so the comparison only counts days when both sides ran.
"""

import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from radar.config import get_settings
from radar.logging import get_logger
from radar.ranker import model as ranker_model
from radar.ranker.features import served
from radar.ranker.model import Model
from radar.recsys.ranking import Ranked

log = get_logger(__name__)

VARIANT_HAND = "hand"
VARIANT_CONTROL = "control"
VARIANT_LEARNED = "learned"
# The narrowest range of scores the model's order is spread over.
_MIN_SPAN = 0.3


@dataclass(frozen=True, slots=True)
class Assignment:
    variant: str
    model: Model | None = None

    @property
    def model_version(self) -> str:
        return self.model.version if self.model else ""


def in_learned_group(user_id: uuid.UUID, share: float) -> bool:
    digest = hashlib.sha256(f"ranker-group:{user_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**32 < share


async def assignment(user_id: uuid.UUID) -> Assignment:
    """The reader's side of the comparison."""
    share = get_settings().ranker_share
    model = await ranker_model.active() if share > 0 else None
    if model is None:
        return Assignment(VARIANT_HAND)
    if in_learned_group(user_id, share):
        return Assignment(VARIANT_LEARNED, model)
    return Assignment(VARIANT_CONTROL, model)


def learned_order(model: Model, ranked: Sequence[Ranked], confidence: float) -> dict[int, float]:
    """Article id -> the score the variety pass should use, in the model's order.

    The model decides the order only. The pass gets evenly spaced scores from
    the best hand score of the pool down to the worst, in the range it was
    tuned for. The span is never narrower than _MIN_SPAN: many articles reach
    the hand blend's cap of 1.0, and equal scores would hand the order back to
    the pass. An empty answer, on any failure, leaves the hand order in place.
    """
    if not ranked:
        return {}
    try:
        predicted = model.scores([served(item.parts, item.score, confidence) for item in ranked])
    except Exception as exc:
        log.warning("ranker_failed", version=model.version, error=type(exc).__name__)
        return {}
    by_model = np.argsort(-predicted, kind="stable")
    top = max(item.score for item in ranked)
    bottom = max(0.0, min(min(item.score for item in ranked), top - _MIN_SPAN))
    steps = np.linspace(top, bottom, num=len(ranked))
    return {
        ranked[int(index)].article_id: round(float(steps[place]), 6)
        for place, index in enumerate(by_model)
    }
