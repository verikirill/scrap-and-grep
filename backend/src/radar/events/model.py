"""One event, its columns in ClickHouse and its form in the Valkey stream.

An event carries ids and numbers only: no titles, no texts, no addresses.
Empty values are zeros, as in the table: 0 for an article or a position, the
nil UUID for a profile or a list, "" for a string.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import orjson

NIL = uuid.UUID(int=0)

# What happened. A mark taken back is the mark's name with "_undo".
SERVED = "served"
IMPRESSION = "impression"
DIGEST_BUILT = "digest_built"
DIGEST_OPENED = "digest_opened"
SUGGESTION_ACCEPTED = "suggestion_accepted"
SUGGESTION_DISMISSED = "suggestion_dismissed"
SHARE_ACCEPTED = "share_accepted"
MCP_CALL = "mcp_call"
UNDO = "_undo"

# Why an article was in a list.
SLOT_RANKED = "ranked"
SLOT_EXPLORE = "explore"
SLOT_NEWEST = "newest"
SLOT_SAVED = "saved"
SLOT_DIGEST = "digest"

COLUMNS = (
    "ts",
    "event_id",
    "user_id",
    "is_guest",
    "event",
    "surface",
    "article_id",
    "source_id",
    "category",
    "request_id",
    "position",
    "slot",
    "profile_id",
    "adaptive",
    "score",
    "features",
    "variant",
    "model_version",
    "detail",
    "value",
)
_TEXT_LIMIT = 64
_MAX_FEATURES = 32
_UUIDS = ("event_id", "user_id", "request_id", "profile_id")
_TEXTS = ("event", "surface", "category", "slot", "variant", "model_version", "detail")
_POSITION_MAX = 65_535
_SOURCE_MAX = 4_294_967_295


@dataclass(frozen=True, slots=True)
class Event:
    event: str
    user_id: uuid.UUID
    is_guest: bool = False
    surface: str = ""
    article_id: int = 0
    source_id: int = 0
    category: str = ""
    request_id: uuid.UUID = NIL
    position: int = 0
    slot: str = ""
    profile_id: uuid.UUID = NIL
    adaptive: bool = False
    score: float = 0.0
    features: Mapping[str, float] = field(default_factory=dict)
    variant: str = ""
    model_version: str = ""
    detail: str = ""
    value: float = 0.0
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: uuid.UUID = field(default_factory=uuid.uuid7)


def to_wire(event: Event) -> bytes:
    """The stream form: one JSON object, the table's columns as keys."""
    data = {name: getattr(event, name) for name in COLUMNS}
    data["features"] = dict(event.features)
    return orjson.dumps(data)


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) > _TEXT_LIMIT:
        raise ValueError(f"bad {name}")
    return value


def _count(value: Any, name: str, limit: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= limit:
        raise ValueError(f"bad {name}")
    return value


def _number(value: Any, name: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"bad {name}")
    return float(value)


def from_wire(raw: bytes) -> tuple[Any, ...]:
    """A table row from the stream form. Raises ValueError on anything malformed:
    a bad entry must be set aside, not stop the batch it came in."""
    try:
        data = orjson.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("not an object")
        values: dict[str, Any] = {name: uuid.UUID(data[name]) for name in _UUIDS}
        values |= {name: _text(data[name], name) for name in _TEXTS}
        ts = datetime.fromisoformat(data["ts"])
        features = data["features"]
    except (KeyError, TypeError, AttributeError, orjson.JSONDecodeError) as exc:
        raise ValueError(str(exc)) from exc
    if ts.tzinfo is None or not values["event"]:
        raise ValueError("bad ts or event")
    if not isinstance(features, dict) or len(features) > _MAX_FEATURES:
        raise ValueError("bad features")
    values["ts"] = ts.astimezone(UTC)
    values["features"] = {_text(key, "feature"): _number(v, key) for key, v in features.items()}
    values["article_id"] = _count(data.get("article_id"), "article_id", 2**63 - 1)
    values["source_id"] = _count(data.get("source_id"), "source_id", _SOURCE_MAX)
    values["position"] = _count(data.get("position"), "position", _POSITION_MAX)
    values["score"] = _number(data.get("score"), "score")
    values["value"] = _number(data.get("value"), "value")
    for name in ("is_guest", "adaptive"):
        if not isinstance(data.get(name), bool):
            raise ValueError(f"bad {name}")
        values[name] = data[name]
    return tuple(values[name] for name in COLUMNS)
