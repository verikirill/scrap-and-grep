"""How many entries of a digest report one event, and what the CVE rule merges.

    uv run python scripts/eval_duplicates.py --out ../docs/eval/duplicates.md

Question (plan, Т3): with sixty-odd sources one incident arrives from several
of them. How often do the example digests carry one event twice, and what
does merging by the CVE and BDU ids the publications name add to the rules
selection already had: one content hash, one headline, close vectors?

Method. The snapshot in data/samples is read and embedded with the hashing
embedder, the default of the stack. Every pair of publications at most three
days apart is checked by the old rules and by the id rule (scoring.
same_vulnerability); the pairs only the id rule merges are listed for a
person to read. Then the entries of each example issue, those of change/,
models/ and vs-analyst/ too, are checked the same way: which of them the id
rule would have merged into another entry.
"""

import argparse
import asyncio
import itertools
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from radar.ai.embedder import HashingEmbedder
from radar.selection.scoring import Mentions, _same_headline, mentions, same_vulnerability
from radar.store.articles import embedding_text
from radar.text import content_hash

ROOT = Path(__file__).resolve().parents[2]
WINDOW = timedelta(days=3)
_ENTRY_RE = re.compile(r"^### \[(.+?)\]\((https?://[^)\s]+)\)", re.MULTILINE)
# The renderer heads every issue with the time it was built. The READMEs, the
# diffs of change/, the analyst's answer and the resumes have no such line.
_ISSUE_RE = re.compile(r"^\*\*Сформирован:\*\*", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Item:
    url: str
    source: str
    title: str
    published: datetime
    hash: str
    named: Mentions


def load(path: Path) -> list[Item]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = json.loads(line)
        items.append(
            Item(
                url=raw["url"],
                source=raw["source"],
                title=raw["title"],
                published=datetime.fromisoformat(raw["published_at"]),
                hash=content_hash(raw["title"], raw.get("content") or raw.get("summary") or ""),
                named=mentions(raw["title"], raw.get("summary") or "", raw.get("content")),
            )
        )
    return items


async def vectors(path: Path) -> list[np.ndarray]:
    embedder = HashingEmbedder()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    texts = [
        embedding_text(row["title"], row.get("summary") or "", row.get("content")) for row in rows
    ]
    return [np.asarray(vector) for vector in await embedder.embed(texts, "document")]


def old_rule(a: Item, b: Item, va: np.ndarray, vb: np.ndarray, threshold: float) -> bool:
    return (
        a.hash == b.hash or _same_headline(a.title, b.title) or float(np.dot(va, vb)) >= threshold
    )


def new_rule(a: Item, b: Item) -> bool:
    return same_vulnerability(a.named, b.named)


def merged_in_examples(
    examples: Path, items: list[Item]
) -> list[tuple[str, int, list[tuple[Item, Item]]]]:
    """Per issue saved under examples, in its subfolders too: its path there,
    its entries and the pairs of them the id rule would have merged. The path
    tells the issues apart: models/ repeats the names of the top level."""
    by_url = {item.url: index for index, item in enumerate(items)}
    digests = []
    for path in sorted(examples.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if not _ISSUE_RE.search(text):
            continue
        entries = [url for _, url in _ENTRY_RE.findall(text)]
        known = [by_url[url] for url in entries if url in by_url]
        merged = []
        for first, second in itertools.combinations(known, 2):
            if new_rule(items[first], items[second]):
                merged.append((items[first], items[second]))
        digests.append((path.relative_to(examples).as_posix(), len(entries), merged))
    return digests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--snapshot", type=Path, default=ROOT / "data" / "samples" / "articles.jsonl"
    )
    parser.add_argument("--examples", type=Path, default=ROOT / "examples")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "eval" / "duplicates.md")
    args = parser.parse_args()

    items = load(args.snapshot)
    vecs = asyncio.run(vectors(args.snapshot))
    threshold = HashingEmbedder.duplicate_threshold
    order = sorted(range(len(items)), key=lambda index: items[index].published)
    old_pairs = 0
    added: list[tuple[Item, Item]] = []
    for position, left in enumerate(order):
        for right in order[position + 1 :]:
            a, b = items[left], items[right]
            if b.published - a.published > WINDOW:
                break
            old = old_rule(a, b, vecs[left], vecs[right], threshold)
            old_pairs += old
            if not old and new_rule(a, b):
                added.append((a, b))

    digests = merged_in_examples(args.examples, items)

    lines = [
        "# Склейка дублей: снимок и примеры выпусков",
        "",
        f"Снимок `data/samples/articles.jsonl`: {len(items)} публикаций, пары не дальше "
        f"{WINDOW.days} дней друг от друга. Эмбеддер - хеширующий, порог {threshold}.",
        "",
        f"- Старые правила (хеш, заголовок, близость векторов): {old_pairs} пар.",
        f"- Правило по номерам CVE и БДУ добавляет: {len(added)} пар.",
        "",
        "## Записи примеров, которые правило по номерам склеило бы",
        "",
        "| Выпуск | Записей | Склеилось бы | Пары |",
        "|---|---|---|---|",
    ]
    for name, count, merged in digests:
        pairs = "; ".join(
            f"{a.title[:60]} ({a.source}) + {b.title[:60]} ({b.source})" for a, b in merged
        )
        lines.append(f"| `{name}` | {count} | {len(merged)} | {pairs or '-'} |")
    lines += [
        "",
        "## Пары снимка, которые склеивает только правило по номерам",
        "",
        "| Общие номера | Первая | Вторая |",
        "|---|---|---|",
    ]
    for a, b in added:
        shared = ", ".join(sorted(a.named.ids & b.named.ids)[:3])
        lines.append(f"| {shared} | {a.title[:90]} ({a.source}) | {b.title[:90]} ({b.source}) |")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"old {old_pairs}, added {len(added)}; digests:")
    for name, count, merged in digests:
        print(f"  {name}: {count} entries, {len(merged)} merged")


if __name__ == "__main__":
    main()
