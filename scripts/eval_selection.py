# /// script
# requires-python = ">=3.12"
# ///
"""The selection against a person's grades: is the assistant as good as an analyst?

1. A template for the person, from a digest's candidates (GET /api/v1/digests/{id}):

    uv run scripts/eval_selection.py template digest.json docs/eval/human/ics-week.csv

   One row per candidate, shuffled, without the model's grade: the person fills
   grade (0-3, the same scale as the model), must (1 for "had to be in the
   digest") and, for an attack or a vulnerability, priority (high, medium, low).

2. The comparison, once the file is filled:

    uv run scripts/eval_selection.py score digest.json docs/eval/human/ics-week.csv

   Precision of the digest, recall of the must-haves, nDCG@20 of its order,
   agreement of the model's grades with the person's (quadratic weighted
   kappa) and of the priorities, as a Markdown table.
"""

import csv
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

GRADES = range(4)
NDCG_DEPTH = 20
# A grade from which a candidate is worth the reader's time: "relevant" and up.
RELEVANT = 2
FIELDS = [
    "article_id",
    "title",
    "source",
    "published_at",
    "url",
    "grade",
    "must",
    "priority",
    "note",
]


def candidates(digest: dict[str, Any]) -> list[dict[str, Any]]:
    """Every candidate of the digest, the selected ones in the digest's order first.

    A rejected copy of a selected story is `merged`: the digest has its story
    and keeps its link, so a person's must on it is not a miss."""
    chosen = [
        {**item, "selected": True, "merged": False, "rank": rank}
        for rank, item in enumerate(
            (item for topic in digest["topics"] for item in topic["items"]), start=1
        )
    ]
    copies = {copy["url"] for item in chosen for copy in item.get("duplicates") or []}
    left = [
        {**item, "selected": False, "merged": item["url"] in copies, "rank": None}
        for item in digest.get("rejected", [])
    ]
    return chosen + left


def template(digest_path: Path, out: Path) -> None:
    rows = candidates(json.loads(digest_path.read_text(encoding="utf-8")))
    # Shuffled and without the model's grade: the person grades blind.
    random.Random(digest_path.name).shuffle(rows)  # noqa: S311 - an order, not a secret
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "article_id": row["article_id"],
                    "title": row["title"],
                    "source": row["source_name"],
                    "published_at": row["published_at"][:10],
                    "url": row["url"],
                }
            )
    print(f"{len(rows)} candidates to grade written to {out}")


def human_grades(path: Path) -> dict[int, dict[str, Any]]:
    graded = {}
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row.get("grade", "").strip() == "":
                continue
            grade = int(row["grade"])
            if grade not in GRADES:
                raise SystemExit(f"article {row['article_id']}: grade {grade} is not 0-3")
            graded[int(row["article_id"])] = {
                "grade": grade,
                "must": row.get("must", "").strip() in {"1", "да", "yes"},
                "priority": row.get("priority", "").strip() or None,
            }
    return graded


def ndcg(ranked: list[int], gains: dict[int, int], depth: int = NDCG_DEPTH) -> float | None:
    """nDCG of the digest's order against the person's grades (gain 2^g - 1)."""

    def dcg(grades: list[int]) -> float:
        return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(grades[:depth]))

    ideal = dcg(sorted(gains.values(), reverse=True))
    return dcg([gains.get(article, 0) for article in ranked]) / ideal if ideal else None


def weighted_kappa(pairs: list[tuple[int, int]]) -> float | None:
    """Quadratic weighted kappa of two graders on the 0-3 scale."""
    if len(pairs) < 2:
        return None
    n = len(GRADES)
    observed = [[0.0] * n for _ in range(n)]
    for a, b in pairs:
        observed[a][b] += 1
    rows = [sum(observed[i]) for i in range(n)]
    cols = [sum(observed[i][j] for i in range(n)) for j in range(n)]
    total = len(pairs)
    weight = [[(i - j) ** 2 / (n - 1) ** 2 for j in range(n)] for i in range(n)]
    seen = sum(weight[i][j] * observed[i][j] for i in range(n) for j in range(n))
    expected = sum(weight[i][j] * rows[i] * cols[j] / total for i in range(n) for j in range(n))
    return 1 - seen / expected if expected else None


def score(digest_path: Path, grades_path: Path) -> None:
    digest = json.loads(digest_path.read_text(encoding="utf-8"))
    rows = candidates(digest)
    human = human_grades(grades_path)
    labeled = [row for row in rows if row["article_id"] in human]
    chosen = [row for row in labeled if row["selected"]]
    must = [row for row in labeled if human[row["article_id"]]["must"]]
    ranked = [row["article_id"] for row in rows if row["selected"]]
    gains = {article: data["grade"] for article, data in human.items()}
    pairs = [
        (int(row["relevance"]), human[row["article_id"]]["grade"])
        for row in labeled
        if row.get("relevance") is not None
    ]
    with_priority = [
        row for row in chosen if row.get("priority") and human[row["article_id"]]["priority"]
    ]

    def share(part: int, whole: int) -> str:
        return f"{part} из {whole} ({part / whole:.0%})" if whole else "нет данных"

    precision = sum(human[row["article_id"]]["grade"] >= RELEVANT for row in chosen)
    found = sum(row["selected"] or row["merged"] for row in must)
    same_grade = sum(model == person for model, person in pairs)
    same_priority = sum(
        row["priority"] == human[row["article_id"]]["priority"] for row in with_priority
    )
    quality = ndcg(ranked, gains)
    kappa = weighted_kappa(pairs)
    name = digest.get("title") or digest.get("profile_name")
    print(f"Выпуск «{name}»: размечено {len(labeled)} из {len(rows)} кандидатов\n")
    print("| Метрика | Значение |")
    print("|---|---|")
    print(f"| Точность: записей выпуска с оценкой человека 2-3 | {share(precision, len(chosen))} |")
    print(f"| Полнота: «обязательных» по мнению человека в выпуске | {share(found, len(must))} |")
    print(
        f"| nDCG@{NDCG_DEPTH} порядка выпуска | {quality:.2f} |"
        if quality is not None
        else f"| nDCG@{NDCG_DEPTH} | нет данных |"
    )
    print(f"| Оценка модели совпала с человеком | {share(same_grade, len(pairs))} |")
    print(
        f"| Взвешенная каппа оценок модели и человека | {kappa:.2f} |"
        if kappa is not None
        else "| Взвешенная каппа | нет данных |"
    )
    print(f"| Приоритет атак и уязвимостей совпал | {share(same_priority, len(with_priority))} |")


def main() -> None:
    # A Windows console would print the table in its own code page.
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if len(sys.argv) != 4 or sys.argv[1] not in {"template", "score"}:
        raise SystemExit(__doc__)
    mode, digest, grades = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    (template if mode == "template" else score)(digest, grades)


if __name__ == "__main__":
    main()
