"""Reading times and pictures that are not known yet are found in the background."""

from collections.abc import Iterable

from radar.ingest.measure import MEASURE_BATCH
from radar.logging import get_logger
from radar.worker.tasks import measure_articles

log = get_logger(__name__)


async def measure_soon(article_ids: Iterable[int]) -> None:
    """Have the pages of these articles read for their length and picture; the next
    view shows them."""
    ids = list(dict.fromkeys(article_ids))[:MEASURE_BATCH]
    if not ids:
        return
    try:
        await measure_articles.kiq(ids)
    except Exception as exc:
        # The page is only missing a reading time; nothing else waits on it.
        log.warning("measure_not_queued", error=type(exc).__name__)
