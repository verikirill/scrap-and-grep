"""Adaptive profiles learn in the background, after marks and impressions."""

import uuid

from radar.cache import Cache
from radar.logging import get_logger
from radar.recsys.adapt import SKIP_WEIGHT
from radar.worker.tasks import adapt_profiles

log = get_logger(__name__)

# Impressions arrive every few seconds while the reader scrolls; one run per
# this many seconds is enough for what they say.
IMPRESSIONS_ADAPT_EVERY = 300


async def adapt_soon(user_id: uuid.UUID) -> None:
    """Queue a recomputation of the reader's adaptive profiles."""
    try:
        await adapt_profiles.kiq(str(user_id))
    except Exception as exc:
        # The marks are saved; the profiles catch up with the next one.
        log.warning("adaptation_not_queued", error=type(exc).__name__)


async def adapt_after_impressions(cache: Cache, user_id: uuid.UUID) -> None:
    # While scrolling past counts for nothing (recsys.adapt), impressions
    # change nothing a recomputation would find.
    if SKIP_WEIGHT == 0:
        return
    if not await cache.hit_rate_limit(f"adapt-seen:{user_id}", 1, IMPRESSIONS_ADAPT_EVERY):
        await adapt_soon(user_id)
