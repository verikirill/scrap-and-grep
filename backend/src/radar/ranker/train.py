"""Train the feed ranker on what readers did with what they were shown.

A training example is an article of a served feed list that the reader saw:
it has an impression or a mark in that same list within a day of serving.
Its features are the ones recorded when it was served, never what the
browser reported. The label grades what the reader did:

    0 disliked or hid, 1 only seen, 2 opened, 3 liked, 4 saved

A list is a query group for LambdaRank (LightGBM). Readers open what is on
top more often, whatever it is; the place goes to LightGBM as a position,
so it learns that pull apart instead of mistaking it for relevance.

The last three full days are held out. On the lists of those days that the
hand blend served (a model's own lists would be ranked in its favour), the
model and the hand blend both order every list, and nDCG@20 over the
readers' own labels decides. The gain is averaged per reader, and a
bootstrap over readers must keep it above zero: many lists of one reader
are not many readers. Ties are broken at random for both, not by the served
order, which carries the clicks' pull to the top. A model already on is
retired once it loses by the margin on enough lists.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import lightgbm as lgb
import numpy as np
from sqlalchemy import select, update

from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import RankerModel
from radar.events import clickhouse
from radar.logging import get_logger
from radar.ranker import model as ranker_model
from radar.ranker.features import FEATURES, matrix, position_band
from radar.ranker.model import STATUS_ACTIVE, STATUS_REJECTED, STATUS_RETIRED
from radar.ranker.serving import VARIANT_LEARNED

log = get_logger(__name__)

LABEL_REJECTED, LABEL_SEEN, LABEL_OPENED, LABEL_LIKED, LABEL_SAVED = range(5)
# What a reader did with a list counts for a day after it was served.
WINDOW = timedelta(hours=24)
HOLDOUT_DAYS = 3
DEPTH = 20
# Less than this and a win is noise.
MIN_TRAIN_LISTS = 200
MIN_HOLDOUT_LISTS = 50
MIN_HOLDOUT_READERS = 5
MIN_ACTIONS = 300
# nDCG@20 the model must gain over the hand blend to be switched on, and lose
# to be switched off.
MARGIN = 0.01
BOOTSTRAP = 1000
MAX_ROWS = 2_000_000
ROUNDS = 200
PARAMS: dict[str, Any] = {
    "objective": "lambdarank",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.9,
    "lambdarank_truncation_level": 30,
    "num_threads": 2,
    "seed": 7,
    "deterministic": True,
    "force_row_wise": True,
    "verbose": -1,
}
_SCORE = FEATURES.index("score")

# Newest first: past MAX_ROWS the oldest lists go, never the held-out days.
# "newest" lists are the cold start, ranked by date and not by anything here.
_QUERY = """
SELECT s.request_id, s.user_id, s.list_variant, s.place, s.served_features, s.served_at,
       multiIf(a.rejected, 0, a.saved, 4, a.liked, 3, a.opened, 2, 1) AS label
FROM
(
    SELECT user_id, request_id, article_id,
           any(variant) AS list_variant,
           min(position) AS place,
           argMin(features, ts) AS served_features,
           min(ts) AS served_at
    FROM events
    WHERE event = 'served' AND surface = 'feed' AND position > 0 AND slot != 'newest'
      AND ts >= {start:DateTime64(3, 'UTC')} AND ts < {served_until:DateTime64(3, 'UTC')}
    GROUP BY user_id, request_id, article_id
) AS s
INNER JOIN
(
    SELECT user_id, request_id, article_id,
           countIf(event IN ('dislike', 'hide')) > 0 AS rejected,
           countIf(event = 'save') > 0 AS saved,
           countIf(event = 'like') > 0 AS liked,
           countIf(event = 'open') > 0 AS opened,
           min(ts) AS acted_at
    FROM events
    WHERE event IN ('impression', 'open', 'like', 'save', 'dislike', 'hide')
      AND surface = 'feed'
      AND ts >= {start:DateTime64(3, 'UTC')} AND ts < {end:DateTime64(3, 'UTC')}
    GROUP BY user_id, request_id, article_id
) AS a USING (user_id, request_id, article_id)
WHERE a.acted_at < s.served_at + INTERVAL 1 DAY
ORDER BY s.served_at DESC
LIMIT {limit:UInt64}
"""

Row = tuple[Any, Any, str, int, dict[str, float], datetime, int]


@dataclass(frozen=True, slots=True)
class Lists:
    """Served lists, one after another in time order, with what was seen in them."""

    features: np.ndarray
    labels: np.ndarray
    positions: np.ndarray
    # Per list: its rows, when it was served, to whom, by which ranker.
    sizes: np.ndarray
    served_at: list[datetime] = field(default_factory=list)
    readers: list[Any] = field(default_factory=list)
    variants: list[str] = field(default_factory=list)

    @property
    def rows(self) -> int:
        return len(self.labels)

    def starts(self) -> np.ndarray:
        return np.concatenate(([0], np.cumsum(self.sizes)[:-1])).astype(int)

    def take(self, keep: Sequence[bool]) -> Lists:
        """The lists where `keep` is true."""
        kept = np.asarray(keep, dtype=bool)
        mask = np.repeat(kept, self.sizes)
        return Lists(
            self.features[mask],
            self.labels[mask],
            self.positions[mask],
            self.sizes[kept],
            [value for value, on in zip(self.served_at, kept, strict=True) if on],
            [value for value, on in zip(self.readers, kept, strict=True) if on],
            [value for value, on in zip(self.variants, kept, strict=True) if on],
        )


def assemble(rows: Sequence[Row]) -> Lists:
    """Lists from (list id, reader, ranker, position, features, served at, label) rows."""
    groups: dict[Any, list[Row]] = {}
    for row in rows:
        groups.setdefault(row[0], []).append(row)
    # A list of one article has nothing to order.
    ordered = sorted(
        (items for items in groups.values() if len(items) > 1),
        key=lambda items: min(item[5] for item in items),
    )
    flat = [item for items in ordered for item in sorted(items, key=lambda item: item[3])]
    return Lists(
        features=matrix([item[4] for item in flat]),
        labels=np.array([item[6] for item in flat], dtype=np.int32),
        positions=np.array([item[3] for item in flat], dtype=np.int32),
        sizes=np.array([len(items) for items in ordered], dtype=np.int32),
        served_at=[min(item[5] for item in items) for items in ordered],
        readers=[items[0][1] for items in ordered],
        variants=[items[0][2] for items in ordered],
    )


def holdout_from(end: datetime) -> datetime:
    """Lists served after this are held out: the last full days with a day to act on."""
    return end - WINDOW - timedelta(days=HOLDOUT_DAYS)


async def load(start: datetime, end: datetime) -> Lists:
    async with clickhouse.connect() as client:
        result = await client.query(
            _QUERY,
            parameters={
                "start": start,
                "served_until": end - WINDOW,
                "end": end,
                "limit": MAX_ROWS,
            },
        )
        rows = result.result_rows
    if len(rows) >= MAX_ROWS:
        log.warning("ranker_rows_cut", limit=MAX_ROWS)
    return assemble(
        [
            (row[0], row[1], row[2], row[3], row[4], row[5].replace(tzinfo=UTC), row[6])
            for row in rows
        ]
    )


def ndcg(labels_in_order: np.ndarray, depth: int = DEPTH) -> float:
    gains = np.power(2.0, labels_in_order) - 1
    discounts = 1 / np.log2(np.arange(2, min(depth, len(gains)) + 2))
    ideal = np.sort(gains)[::-1][:depth]
    best = float(ideal @ discounts[: len(ideal)])
    return float(gains[:depth] @ discounts[: min(depth, len(gains))]) / best if best else 0.0


def list_ndcg(lists: Lists, scores: np.ndarray, tiebreak: np.ndarray) -> np.ndarray:
    """nDCG@20 of every list ordered by `scores`; NaN where all labels are alike
    and the order cannot matter."""
    values = np.full(len(lists.sizes), np.nan)
    for index, (start, size) in enumerate(zip(lists.starts(), lists.sizes, strict=True)):
        labels = lists.labels[start : start + size]
        if labels.min() == labels.max():
            continue
        order = np.lexsort((tiebreak[start : start + size], -scores[start : start + size]))
        values[index] = ndcg(labels[order])
    return values


def mean_ndcg(lists: Lists, scores: np.ndarray, seed: int = 0) -> float:
    tiebreak = np.random.default_rng(seed).random(lists.rows)
    values = list_ndcg(lists, scores, tiebreak)
    return float(np.nanmean(values)) if np.isfinite(values).any() else 0.0


@dataclass(frozen=True, slots=True)
class Comparison:
    hand: float
    model: float
    # The gain averaged per reader, and the 5th percentile of its bootstrap.
    gain: float
    gain_low: float
    lists: int
    readers: int


def compare(lists: Lists, model_scores: np.ndarray, seed: int = 0) -> Comparison:
    """The model against the hand blend on the same lists, reader by reader."""
    rng = np.random.default_rng(seed)
    tiebreak = rng.random(lists.rows)
    hand = list_ndcg(lists, lists.features[:, _SCORE], tiebreak)
    model = list_ndcg(lists, model_scores, tiebreak)
    counted = np.isfinite(hand)
    by_reader: dict[Any, list[float]] = {}
    for reader, difference, on in zip(lists.readers, model - hand, counted, strict=True):
        if on:
            by_reader.setdefault(reader, []).append(float(difference))
    gains = np.array([np.mean(values) for values in by_reader.values()])
    if len(gains) < MIN_HOLDOUT_READERS:
        low = -np.inf
    else:
        draws = rng.choice(gains, size=(BOOTSTRAP, len(gains)), replace=True).mean(axis=1)
        low = float(np.percentile(draws, 5))
    return Comparison(
        hand=float(np.mean(hand[counted])) if counted.any() else 0.0,
        model=float(np.mean(model[counted])) if counted.any() else 0.0,
        gain=float(gains.mean()) if len(gains) else 0.0,
        gain_low=low,
        lists=int(counted.sum()),
        readers=len(gains),
    )


def fit(lists: Lists, *, debias: bool = True) -> lgb.Booster:
    data = lgb.Dataset(
        lists.features,
        label=lists.labels,
        group=lists.sizes,
        position=np.array([position_band(int(p)) for p in lists.positions], dtype=np.int32)
        if debias
        else None,
        feature_name=list(FEATURES),
        free_raw_data=False,
    )
    return lgb.train(PARAMS, data, num_boost_round=ROUNDS)


def predict(booster: lgb.Booster, lists: Lists) -> np.ndarray:
    return np.asarray(booster.predict(lists.features, num_threads=1), dtype=np.float64)


@dataclass(frozen=True, slots=True)
class Outcome:
    status: str
    note: str
    metrics: dict[str, float]
    lists: int
    rows: int
    booster: lgb.Booster | None = None
    # Whether the model already on still holds against the hand blend.
    keep_active: bool = True


def _rows(lists: Lists) -> list[dict[str, float]]:
    return [dict(zip(FEATURES, map(float, row), strict=True)) for row in lists.features]


def evaluate(lists: Lists, end: datetime, current: ranker_model.Model | None = None) -> Outcome:
    """Fit on all but the last days, compare with the hand blend on those days."""
    if not lists.sizes.size:
        return Outcome(STATUS_REJECTED, "Событий пока нет.", {}, 0, 0)
    held = [moment >= holdout_from(end) for moment in lists.served_at]
    train = lists.take([not on for on in held])
    # Lists a model ordered favour it: only the hand blend's lists judge.
    judged = lists.take(
        [
            on and variant != VARIANT_LEARNED
            for on, variant in zip(held, lists.variants, strict=True)
        ]
    )
    actions = int((train.labels >= LABEL_OPENED).sum())
    metrics: dict[str, float] = {
        "train_lists": float(len(train.sizes)),
        "holdout_lists": float(len(judged.sizes)),
        "actions": float(actions),
    }
    enough_holdout = len(judged.sizes) >= MIN_HOLDOUT_LISTS
    keep = True
    if current is not None and enough_holdout:
        try:
            standing = compare(judged, current.scores(_rows(judged)))
            metrics["current_ndcg"] = standing.model
            keep = standing.gain > -MARGIN
        except Exception as exc:
            log.warning("ranker_current_not_scored", error=type(exc).__name__)
            keep = False
    if len(train.sizes) < MIN_TRAIN_LISTS or not enough_holdout or actions < MIN_ACTIONS:
        note = (
            f"Мало данных: списков для обучения {len(train.sizes)} из {MIN_TRAIN_LISTS}, "
            f"для проверки {len(judged.sizes)} из {MIN_HOLDOUT_LISTS}, "
            f"открытий и отметок {actions} из {MIN_ACTIONS}."
        )
        return Outcome(
            STATUS_REJECTED, note, metrics, len(lists.sizes), lists.rows, keep_active=keep
        )
    booster = fit(train)
    result = compare(judged, predict(booster, judged))
    metrics |= {
        "hand_ndcg": result.hand,
        "model_ndcg": result.model,
        "gain": result.gain,
        "gain_low": max(result.gain_low, -1.0),
        "readers": float(result.readers),
    }
    if result.gain >= MARGIN and result.gain_low > 0:
        note = (
            f"Модель лучше ручных весов на {result.gain:+.3f} nDCG@{DEPTH} "
            f"на последних днях, у {result.readers} читателей."
        )
        status = STATUS_ACTIVE
    else:
        note = (
            f"Модель не обогнала ручные веса: {result.gain:+.3f} nDCG@{DEPTH} "
            f"(нижняя граница {max(result.gain_low, -1.0):+.3f}), нужно {MARGIN:+.3f} "
            "и граница выше нуля."
        )
        status = STATUS_REJECTED
    return Outcome(status, note, metrics, len(lists.sizes), lists.rows, booster, keep)


async def train(now: datetime | None = None) -> RankerModel:
    """One nightly run: load, fit, compare, store the result, switch models."""
    end = now or datetime.now(UTC)
    start = end - timedelta(days=get_settings().ranker_train_days)
    lists = await load(start, end)
    current = await ranker_model.active()
    outcome = await asyncio.to_thread(evaluate, lists, end, current)
    run = RankerModel(
        version=f"{end:%Y%m%d-%H%M%S}",
        status=outcome.status,
        trained_from=start,
        trained_to=holdout_from(end),
        lists=outcome.lists,
        rows=outcome.rows,
        metrics={key: round(value, 4) for key, value in outcome.metrics.items()},
        features=list(FEATURES),
        model=outcome.booster.model_to_string() if outcome.booster else "",
        note=outcome.note,
    )
    async with session_scope() as session:
        if outcome.status == STATUS_ACTIVE or not outcome.keep_active:
            await session.execute(
                update(RankerModel)
                .where(RankerModel.status == STATUS_ACTIVE)
                .values(status=STATUS_RETIRED)
            )
            await session.flush()
        session.add(run)
    ranker_model.forget()
    log.info(
        "ranker_trained",
        version=run.version,
        status=run.status,
        lists=run.lists,
        **{key: round(value, 4) for key, value in outcome.metrics.items()},
    )
    return run


async def history(limit: int = 5) -> list[RankerModel]:
    """The latest runs, newest first, without the model text."""
    async with session_scope() as session:
        rows = await session.scalars(
            select(RankerModel).order_by(RankerModel.created_at.desc()).limit(limit)
        )
        return list(rows)
