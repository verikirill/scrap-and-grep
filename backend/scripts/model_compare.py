"""Build the example week's digests on the model the environment names.

The comparison of models in examples/models is made of these runs: the same
profiles, the same week and the same graph, only the model changes. Each run
is a separate process, because the model is read from the settings once:

    docker exec -i -e RADAR_LLM_MODEL=gemma4:31b -e RADAR_LLM_REASONING=off \
        radar-api-3 python - < backend/scripts/model_compare.py
    docker exec radar-api-3 cat /tmp/model_compare.json > examples/models/gemma4-31b.json

The digests are built for the demo account and deleted afterwards: the run
leaves its numbers, not rows in someone's history. Next to the time it keeps
the tokens of each digest, the speed of writing where the server tells it,
and the memory Ollama gave the model (on the card and in all).
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

from radar.ai.factory import get_chat, get_intelligence
from radar.ai.llm import Usage
from radar.auth import DEMO_EMAIL
from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import Digest, Profile, User
from radar.domain import ProfileSpec
from radar.pipeline.runner import report_failure, run_digest
from radar.render.markdown import render_markdown
from radar.store import digests as digest_store
from radar.views import digest_view

# The week of data/samples/articles.jsonl and of examples/: every model reads
# the same publications.
PERIOD_START = datetime.fromisoformat("2026-09-25T00:00:00+03:00")
PERIOD_END = datetime.fromisoformat("2026-10-02T16:00:00+03:00")
PROFILES = ("Специалист по ИБ АСУ ТП", "Руководство и сотрудники: кибербезопасность")
# The api container's root is read-only; /tmp is the place a script may write.
OUT = Path("/tmp/model_compare.json")  # noqa: S108


async def build(name: str) -> dict[str, Any]:
    async with session_scope() as session:
        row = await session.scalar(
            select(Profile)
            .join(User, User.id == Profile.user_id)
            .where(Profile.name == name, User.email == DEMO_EMAIL)
        )
        if row is None:
            raise SystemExit(f"no example profile {name!r} in the demo account")
        created = await digest_store.create(
            session,
            user_id=row.user_id,
            profile_id=row.id,
            profile=ProfileSpec.model_validate(row.spec),
            profile_version=row.version,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        digest_id = created.id

    chat = get_chat()
    before = chat.usage.copy() if chat else None
    started = time.monotonic()
    try:
        await run_digest(digest_id)
        seconds = round(time.monotonic() - started, 1)
        used = chat.usage.since(before) if chat and before else None
        async with session_scope() as session:
            loaded = await digest_store.get(session, digest_id, full=True)
            if loaded is None:
                raise SystemExit("the digest is gone")
            view = digest_view(loaded)
    except Exception as exc:
        await report_failure(digest_id, exc)
        raise
    finally:
        async with session_scope() as session:
            if (row := await session.get(Digest, digest_id)) is not None:
                await session.delete(row)

    items = [
        {
            "article_id": item.article_id,
            "url": item.url,
            "headline": item.headline,
            "kind": item.kind,
            "priority": item.priority,
            "tags": list(item.tags),
            "unsupported": list(item.unsupported),
            "references": [reference.id for reference in item.references if reference.found],
        }
        for topic in view.topics
        for item in topic.items
    ]
    return {
        "profile": name,
        "seconds": seconds,
        "usage": _usage(used, seconds),
        "title": view.title,
        "topics": [topic.title for topic in view.topics],
        "stats": view.stats,
        "items": items,
        "markdown": render_markdown(view),
    }


def _usage(used: Usage | None, seconds: float) -> dict[str, Any] | None:
    if used is None:
        return None
    speed = used.tokens_per_second
    return {
        "requests": used.requests,
        "input_tokens": used.input_tokens,
        "output_tokens": used.output_tokens,
        # One request's writing, without the queue; Ollama only.
        "tokens_per_second": round(speed, 1) if speed else None,
        # Everything the model wrote over the whole build, any server.
        "output_per_build_second": round(used.output_tokens / seconds, 1) if seconds else None,
    }


async def loaded_models() -> list[dict[str, Any]]:
    """What Ollama keeps in memory now: the size of each model and the part on
    the card. Empty when the model is not in Ollama (vLLM, another server)."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            reply = await client.get(f"{get_settings().ollama_base_url}/api/ps")
            reply.raise_for_status()
    except httpx.HTTPError:
        return []
    return [
        {
            "name": model.get("name"),
            "size_gb": round(model.get("size", 0) / 1e9, 2),
            "on_card_gb": round(model.get("size_vram", 0) / 1e9, 2),
            "context": model.get("context_length"),
        }
        for model in reply.json().get("models", [])
    ]


async def main() -> None:
    model = get_intelligence().name
    print(f"model {model}", flush=True)
    runs = []
    for name in PROFILES:
        run = await build(name)
        print(f"  {name}: {len(run['items'])} items, {run['seconds']} s", flush=True)
        if run["usage"]:
            print(f"    {run['usage']}", flush=True)
        runs.append(run)
    memory = await loaded_models()
    print(f"memory {memory}", flush=True)
    OUT.write_text(
        json.dumps(
            {"model": model, "runs": runs, "memory": memory},
            ensure_ascii=False,
            indent=1,
            default=str,
        ),
        encoding="utf-8",
    )


asyncio.run(main())
