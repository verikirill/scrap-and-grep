# /// script
# requires-python = ">=3.12"
# ///
"""A sample of the week that retrieval left out, for a person to grade.

The labeling in docs/eval/human grades the 60 candidates retrieval found: it
measures the grading, not what retrieval never brought. This sample does. Out
of the week's publications that are not among a digest's candidates it takes
the ones whose title or text names a keyword of the profile ("keyword") and a
random draw of the rest ("random"), shuffled together:

    uv run scripts/recall_sample.py docs/eval/human/ics-security-engineer.digest.json \
        docs/eval/recall/ics-security-engineer.csv

The person fills grade and must as in docs/eval/human/README.md. A must here
is a story the digest lost before any model saw it; the stratum column lets
the count be scaled back to the whole week.
"""

import csv
import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path

SAMPLES = Path("data/samples/articles.jsonl")
KEYWORD = 50
RANDOM = 30
FIELDS = ["article_id", "title", "source", "published_at", "url", "stratum", "grade", "must", "note"]


def when(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    digest_path, out = Path(sys.argv[1]), Path(sys.argv[2])
    digest = json.loads(digest_path.read_text(encoding="utf-8"))
    start, end = when(digest["period_start"]), when(digest["period_end"])
    chosen = [item for topic in digest["topics"] for item in topic["items"]]
    taken = {item["url"] for item in chosen + digest["rejected"]}
    taken |= {copy["url"] for item in chosen for copy in item.get("duplicates") or []}
    # Whole words: "OT" must not match "not".
    words = [word for interest in digest["profile"]["interests"] for word in interest["keywords"]]
    keywords = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, words)) + r")(?!\w)", re.I)
    week = []
    for number, line in enumerate(SAMPLES.read_text(encoding="utf-8").splitlines(), start=1):
        article = json.loads(line)
        if article["url"] in taken or not start <= when(article["published_at"]) < end:
            continue
        text = f"{article['title']} {article.get('summary') or ''} {article.get('content') or ''}"
        week.append((number, article, bool(keywords.search(text))))
    draw = random.Random(digest_path.name)  # noqa: S311 - a sample, not a secret
    named = [row for row in week if row[2]]
    rest = [row for row in week if not row[2]]
    sample = [(row, "keyword") for row in draw.sample(named, min(KEYWORD, len(named)))]
    sample += [(row, "random") for row in draw.sample(rest, min(RANDOM, len(rest)))]
    draw.shuffle(sample)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, FIELDS)
        writer.writeheader()
        for (number, article, _), stratum in sample:
            writer.writerow(
                {
                    # The line of data/samples: the snapshot has no ids of its own.
                    "article_id": number,
                    "title": article["title"],
                    "source": article["source"],
                    "published_at": article["published_at"][:10],
                    "url": article["url"],
                    "stratum": stratum,
                }
            )
    print(
        f"{len(sample)} of {len(week)} left-out publications written to {out}: "
        f"keyword {min(KEYWORD, len(named))} of {len(named)}, random {min(RANDOM, len(rest))} of {len(rest)}"
    )


if __name__ == "__main__":
    main()
