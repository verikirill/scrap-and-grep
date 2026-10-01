"""The active learned ranker, loaded once per process and refreshed when it changes."""

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
from sqlalchemy import select

from radar.db import session_scope
from radar.db.models import RankerModel
from radar.logging import get_logger
from radar.ranker import features

log = get_logger(__name__)

STATUS_ACTIVE = "active"
STATUS_REJECTED = "rejected"
STATUS_RETIRED = "retired"
# A new model reaches every api replica within this long.
_REFRESH_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class Model:
    version: str
    booster: lgb.Booster
    features: tuple[str, ...]

    def scores(self, rows: Sequence[Mapping[str, float]]) -> np.ndarray:
        # One thread: a feed is a few hundred rows, and the api serves many at once.
        predicted = self.booster.predict(features.matrix(rows, self.features), num_threads=1)
        return np.asarray(predicted, dtype=np.float64)


def load(version: str, text: str, names: Sequence[str]) -> Model:
    return Model(version, lgb.Booster(model_str=text), tuple(names))


_checked_at = -math.inf
_current: Model | None = None


async def active() -> Model | None:
    """The model switched on, if any. A failed refresh keeps the one in hand."""
    global _checked_at, _current
    if time.monotonic() - _checked_at < _REFRESH_SECONDS:
        return _current
    _checked_at = time.monotonic()
    try:
        async with session_scope() as session:
            row = (
                await session.execute(
                    select(RankerModel.version, RankerModel.features).where(
                        RankerModel.status == STATUS_ACTIVE
                    )
                )
            ).first()
            if row is None:
                _current = None
            elif _current is None or _current.version != row.version:
                text = await session.scalar(
                    select(RankerModel.model).where(RankerModel.version == row.version)
                )
                _current = load(row.version, text or "", row.features)
    except Exception as exc:
        log.warning("ranker_not_loaded", error=f"{type(exc).__name__}: {exc}"[:200])
    return _current


def forget() -> None:
    """Drop the loaded model, so the next call reads the table again."""
    global _checked_at, _current
    _checked_at, _current = -math.inf, None
