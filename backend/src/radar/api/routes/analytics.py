"""The administrator's analytics: what readers were shown and what they did."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from clickhouse_connect.driver.exceptions import DatabaseError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from radar.api.deps import AdminUser, SessionDep, SettingsDep, user_rate_limit
from radar.db.models import Source
from radar.events import analytics, enabled, writer
from radar.logging import get_logger
from radar.ranker import model as ranker_model
from radar.ranker import train

router = APIRouter(tags=["analytics"])
log = get_logger(__name__)

# Nine queries a press; the page is for one or two people.
_limit = Depends(
    user_rate_limit("analytics", lambda settings: settings.preview_rate_limit_per_minute)
)


class Rates(BaseModel):
    seen: int
    opened: int
    liked: int
    rejected: int
    ctr: float
    ctr_low: float
    ctr_high: float
    like_rate: float
    reject_rate: float
    # Enough seen articles for the rate to mean something.
    enough: bool


class Totals(Rates):
    readers: int
    served: int
    digests_built: int
    digests_opened: int
    mcp_calls: int
    suggestions_accepted: int
    suggestions_dismissed: int


class DayOut(Rates):
    day: date
    readers: int


class SlotOut(Rates):
    slot: str


class SourceOut(Rates):
    source_id: int
    name: str


class CategoryOut(Rates):
    category: str


class CohortOut(Rates):
    adaptive: bool
    readers: int


class VariantOut(Rates):
    variant: str
    readers: int


class Queue(BaseModel):
    """Events waiting in Valkey for ClickHouse, and those set aside as unreadable."""

    waiting: int
    set_aside: int


class RankerRun(BaseModel):
    version: str
    # "active", "rejected" or "retired".
    status: str
    created_at: datetime
    lists: int
    rows: int
    hand_ndcg: float | None
    model_ndcg: float | None
    note: str


class RankerOut(BaseModel):
    """The learned ranker: the share of readers it serves when on, and the last runs."""

    share: float
    active: str | None
    runs: list[RankerRun]


class AnalyticsOut(BaseModel):
    enabled: bool
    start: date
    end: date
    guests: bool
    totals: Totals | None = None
    previous: Totals | None = None
    daily: list[DayOut] = []
    slots: list[SlotOut] = []
    sources_best: list[SourceOut] = []
    sources_rejected: list[SourceOut] = []
    categories: list[CategoryOut] = []
    adaptation: list[CohortOut] = []
    variants: list[VariantOut] = []
    last_event_at: datetime | None = None
    queue: Queue | None = None
    ranker: RankerOut | None = None


@router.get("/analytics/overview", dependencies=[_limit])
async def get_overview(
    user: AdminUser,
    session: SessionDep,
    settings: SettingsDep,
    days: Annotated[int, Query(ge=1, le=90)] = 30,
    guests: bool = True,
) -> AnalyticsOut:
    """Totals, days, places in the feed, sources, categories and the two comparisons."""
    end = datetime.now(UTC).date()
    period = analytics.Period(end - timedelta(days=days - 1), end, guests)
    if not enabled():
        return AnalyticsOut(enabled=False, start=period.start, end=period.end, guests=guests)
    try:
        found = await analytics.overview(period)
    except DatabaseError as exc:
        log.warning("analytics_unavailable", error=f"{type(exc).__name__}: {exc}"[:300])
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Хранилище событий не отвечает, попробуйте через минуту.",
        ) from exc
    ids = {row["source_id"] for row in found["sources_best"] + found["sources_rejected"]}
    names = dict(
        (await session.execute(select(Source.id, Source.name).where(Source.id.in_(ids)))).all()
    )
    for key in ("sources_best", "sources_rejected"):
        found[key] = [
            row | {"name": names.get(row["source_id"], f"Источник {row['source_id']}")}
            for row in found[key]
        ]
    runs = await train.history()
    return AnalyticsOut(
        enabled=True,
        start=period.start,
        end=period.end,
        guests=guests,
        queue=Queue(**await writer.backlog()),
        ranker=RankerOut(
            share=settings.ranker_share,
            active=current.version if (current := await ranker_model.active()) else None,
            runs=[
                RankerRun(
                    version=run.version,
                    status=run.status,
                    created_at=run.created_at,
                    lists=run.lists,
                    rows=run.rows,
                    hand_ndcg=run.metrics.get("hand_ndcg"),
                    model_ndcg=run.metrics.get("model_ndcg"),
                    note=run.note,
                )
                for run in runs
            ],
        ),
        **found,
    )
