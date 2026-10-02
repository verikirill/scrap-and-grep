"""Run the organizers' dataset examples through the digest's model steps.

For each of the 21 examples in docs/task/dataset_v4.0.json the page is read
the way the stack reads a source (a Telegram post through its channel page),
graded and written for the example's audience with the same model, tool and
check as a digest, and the result is written next to what the dataset wants.

Run inside the api container, which has the model, the key and the bases:

    docker exec -i radar-api-3 sh -c 'cat > /tmp/dataset.json' < docs/task/dataset_v4.0.json
    docker exec -i radar-api-3 python - < backend/scripts/dataset_run.py
    docker exec radar-api-3 cat /tmp/dataset_run.json > examples/dataset/run.json

A page the site will not give a bot (401, 403) is reported as such: it is not
replaced by the dataset's own text, which would grade the answer by itself.
"""

import asyncio
import json
import re
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from radar.ai.factory import get_intelligence
from radar.cards import (
    PRIORITY_LABELS,
    TAG_LABELS,
    card_ids,
    check_entry,
    defang,
    priority,
    priority_reason,
    source_text,
)
from radar.db import session_scope
from radar.domain import ArticleRef, Candidate, GradedCandidate, SelectedItem
from radar.ingest import telegram
from radar.ingest.net import build_client, safe_get
from radar.ingest.pages import page_text
from radar.seed import DEFAULT_PROFILES
from radar.text import content_hash, detect_language
from radar.views import ItemView
from radar.vulns.lookup import lookup

_POST_RE = re.compile(r"t\.me/(\w+)/(\d+)")
_TITLE_RE = re.compile(
    r"<meta[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)|<title[^>]*>([^<]+)",
    re.IGNORECASE,
)


async def read(client: Any, url: str) -> tuple[str, str, tuple[str, ...]] | str:
    """The title, text and cited links of the page, or why there are none."""
    post = _POST_RE.search(url)
    if post:
        name, number = post.group(1), int(post.group(2))
        response = await safe_get(client, f"https://t.me/s/{name}?before={number + 1}")
        found = next(
            (
                item
                for item in telegram.parse_channel_page(response.text, name).posts
                if item.id == number
            ),
            None,
        )
        if found is None:
            return "пост не найден на странице канала"
        text = "\n".join(found.lines)
        return found.lines[0][:200] if found.lines else name, text, found.links
    response = await safe_get(client, url)
    for _ in range(2):
        # research.checkpoint.com answers 202 now and then while it decides about a bot.
        if response.status_code != 202:
            break
        await asyncio.sleep(3)
        response = await safe_get(client, url)
    if response.status_code != 200:
        return f"сайт ответил HTTP {response.status_code}"
    text = page_text(str(response.url), response.text) or ""
    if len(text) < 200:
        return "на странице нет текста статьи (её собирает браузер)"
    title = _TITLE_RE.search(response.text)
    heading = unescape((title.group(1) or title.group(2)).strip()) if title else url
    return heading, text, ()


async def run_one(client: Any, example: dict[str, Any], number: int) -> dict[str, Any]:
    management = example["audience"] == "management"
    profile = next(
        spec
        for spec in DEFAULT_PROFILES
        if spec.audience == example["audience"]
        and (spec.name.startswith("Руководство") if management else "АСУ" in spec.name)
    )
    pages = [(url, await read(client, url)) for url in example["urls"]]
    readable = [(url, page) for url, page in pages if not isinstance(page, str)]
    result: dict[str, Any] = {
        "example": example,
        "profile": profile.name,
        "pages": [
            {"url": url, "error": page if isinstance(page, str) else None} for url, page in pages
        ],
    }
    if not readable:
        return result
    url, (title, text, links) = readable[0]
    # A story told by two sites is one entry, as in a digest.
    text = "\n\n".join(page[1] for _, page in readable)
    published = (
        datetime.fromisoformat(example["date"]).replace(tzinfo=UTC)
        if example["date"]
        else datetime.now(UTC)
    )
    article = ArticleRef(
        id=number,
        url=url,
        title=title,
        summary=text[:600],
        content=text[:4000],
        source_name=urlsplit(url).hostname or url,
        source_category="security",
        language=detect_language(text),
        published_at=published,
        content_hash=content_hash(title, text),
        links=tuple(links),
    )
    candidate = Candidate(article=article, interest_id=profile.interests[0].id, retrieval_score=0.7)
    intelligence = get_intelligence()
    grade = await intelligence.grade(candidate, profile)
    item = SelectedItem(graded=GradedCandidate(candidate=candidate, grade=grade, score=0.8))
    written = await intelligence.summarize(item, profile, profile.interest(grade.interest_id))
    # The graph's own steps after the model: references for the card's ids, the check.
    source = source_text(article.title, article.summary, article.content)
    ids = card_ids(written, source)
    kept = [r for r in written.references if r.found and (r.id in ids or r.bdu_id in ids)]
    covered = {r.id for r in kept} | {r.bdu_id for r in kept}
    async with session_scope() as session:
        found = await lookup(session, [value for value in ids if value not in covered])
    written = written.model_copy(update={"references": (*kept, *found)})
    evidence = "\n".join([source, *(r.text() for r in written.references if r.found)])
    entry = check_entry(written, evidence)
    level = priority(grade.kind, entry)
    view = ItemView.model_validate(
        {
            "article_id": number,
            "url": url,
            "title": title,
            "headline": entry.headline or title,
            "source_name": article.source_name,
            "source_category": "security",
            "language": article.language,
            "published_at": published,
            "score": 0.8,
            "retrieval_score": 0.7,
            "relevance": grade.relevance,
            "interest_id": grade.interest_id,
            "interest_title": None,
            "reason": grade.reason,
            "summary": entry.summary,
            "why": entry.why,
            "kind": grade.kind,
            "priority": level,
            "attack": entry.attack,
            "vulnerability": entry.vulnerability,
            "tags": list(entry.tags),
            "unsupported": list(entry.unsupported),
            "references": list(entry.references),
        }
    )
    result.update(
        {
            "kind": grade.kind,
            "relevance": grade.relevance,
            "by_model": grade.by_model and entry.by_model,
            "priority": PRIORITY_LABELS[level] if level else "",
            "priority_reason": priority_reason(grade.kind, entry) if level else "",
            "headline": view.headline,
            "summary": entry.summary,
            "why": entry.why,
            "fields": [field.model_dump() for field in view.fields],
            "tags": [TAG_LABELS[tag] for tag in entry.tags],
            "tag_ids": list(entry.tags),
            "links": [defang(link) for link in links],
            "unsupported": list(entry.unsupported),
        }
    )
    return result


# The api container's root is read-only; /tmp is the place a script may write.
DATASET = Path("/tmp/dataset.json")  # noqa: S108
RESULT = Path("/tmp/dataset_run.json")  # noqa: S108


async def run_all(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    async with build_client() as client:
        for number, example in enumerate(examples, start=1):
            try:
                results.append(await run_one(client, example, number))
            except Exception as exc:
                results.append({"example": example, "failed": f"{type(exc).__name__}: {exc}"[:300]})
    return results


def main() -> None:
    examples = json.loads(DATASET.read_text(encoding="utf-8"))
    results = asyncio.run(run_all(examples))
    RESULT.write_text(
        json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )


main()
