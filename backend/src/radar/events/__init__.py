"""Reader events: what was served, seen, opened and marked, kept in ClickHouse.

The API puts an event into a Valkey stream and moves on; a worker task takes
the stream in batches into ClickHouse (see `writer`). PostgreSQL stays the
source of truth for articles, profiles and current marks: an unliked article
loses its row there, while here both the like and the take-back remain, which
is what analytics and a learned ranker need.
"""

from radar.events.emit import emit, enabled
from radar.events.model import NIL, Event

__all__ = ["NIL", "Event", "emit", "enabled"]
