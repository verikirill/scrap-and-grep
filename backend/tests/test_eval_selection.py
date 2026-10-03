"""scripts/eval_selection.py: the selection against a person's grades (К2).

The metrics are checked against independent computations, and the template
and the score against a real digest of docs/eval/human."""

import csv
import importlib.util
import json
import random
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[2]
DIGEST = ROOT / "docs" / "eval" / "human" / "ics-security-engineer.digest.json"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "eval_selection", ROOT / "scripts" / "eval_selection.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


evaluation = _script()


def item(
    article_id: int, relevance: int | None = None, priority: str | None = None
) -> dict[str, Any]:
    return {
        "article_id": article_id,
        "title": f"Статья {article_id}",
        "source_name": "Источник",
        "published_at": "2026-10-01T10:00:00+00:00",
        "url": f"https://example.org/{article_id}",
        "relevance": relevance,
        "priority": priority,
    }


def test_ndcg_of_the_best_order_is_one_and_of_a_worse_one_less() -> None:
    gains = {1: 3, 2: 2, 3: 0}
    assert evaluation.ndcg([1, 2, 3], gains) == pytest.approx(1.0)
    worse = evaluation.ndcg([3, 2, 1], gains)
    # (2^0-1)/1 + (2^2-1)/log2(3) + (2^3-1)/2 against 7 + 3/log2(3).
    assert worse == pytest.approx((3 / 1.5849625 + 7 / 2) / (7 + 3 / 1.5849625), rel=1e-6)
    # Only the first `depth` count, and nothing to find is no answer.
    assert evaluation.ndcg([3, 1], gains, depth=1) == 0.0
    assert evaluation.ndcg([1, 2], {1: 0, 2: 0}) is None


def test_weighted_kappa_is_the_quadratic_cohen_kappa() -> None:
    generator = random.Random(7)  # noqa: S311 - test data, not a secret
    for _ in range(20):
        pairs = [(generator.randint(0, 3), generator.randint(0, 3)) for _ in range(40)]
        model, person = zip(*pairs, strict=True)
        expected = cohen_kappa_score(model, person, labels=[0, 1, 2, 3], weights="quadratic")
        assert evaluation.weighted_kappa(pairs) == pytest.approx(expected)
    assert evaluation.weighted_kappa([(1, 1), (2, 2), (3, 3)]) == pytest.approx(1.0)
    assert evaluation.weighted_kappa([(1, 1)]) is None


def test_the_digest_comes_first_in_its_order_then_the_rest() -> None:
    digest = {
        "topics": [{"items": [item(5), item(3)]}, {"items": [item(9)]}],
        "rejected": [item(1)],
    }
    rows = evaluation.candidates(digest)
    assert [(row["article_id"], row["selected"], row["rank"]) for row in rows] == [
        (5, True, 1),
        (3, True, 2),
        (9, True, 3),
        (1, False, None),
    ]


def test_grades_read_from_the_file(tmp_path: Path) -> None:
    path = tmp_path / "grades.csv"
    path.write_text(
        "article_id,grade,must,priority\n1,3,1,high\n2,0,да,\n3,,1,\n4,2,,low\n",
        encoding="utf-8",
    )
    assert evaluation.human_grades(path) == {
        1: {"grade": 3, "must": True, "priority": "high"},
        2: {"grade": 0, "must": True, "priority": None},
        4: {"grade": 2, "must": False, "priority": "low"},
    }
    path.write_text("article_id,grade\n1,5\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="not 0-3"):
        evaluation.human_grades(path)


def test_the_template_has_every_candidate_shuffled_and_no_model_grade(tmp_path: Path) -> None:
    out = tmp_path / "grades.csv"
    evaluation.template(DIGEST, out)
    again = tmp_path / "again.csv"
    evaluation.template(DIGEST, again)

    digest = json.loads(DIGEST.read_text(encoding="utf-8"))
    expected = {row["article_id"] for row in evaluation.candidates(digest)}
    with out.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert {int(row["article_id"]) for row in rows} == expected
    assert list(rows[0]) == evaluation.FIELDS
    assert all(row["grade"] == "" and row["must"] == "" for row in rows)
    # Blind: not in the digest's order, and the same order every time.
    assert [int(row["article_id"]) for row in rows] != [
        row["article_id"] for row in evaluation.candidates(digest)
    ]
    assert out.read_text(encoding="utf-8") == again.read_text(encoding="utf-8")


def test_the_score_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    digest = {
        "title": "Проверка",
        "topics": [{"items": [item(1, 3, "high"), item(2, 2, "medium"), item(3, 2)]}],
        "rejected": [item(4, 1), item(5, 0), item(6, 1)],
    }
    digest_path = tmp_path / "digest.json"
    digest_path.write_text(json.dumps(digest), encoding="utf-8")
    grades = tmp_path / "grades.csv"
    # The digest: 1 and 2 worth it, 3 not; 4 was a must and left out; 6 not graded.
    grades.write_text(
        "article_id,grade,must,priority\n1,3,1,high\n2,2,,low\n3,1,,\n4,3,1,\n5,0,,\n",
        encoding="utf-8",
    )
    evaluation.score(digest_path, grades)
    table = capsys.readouterr().out

    assert "размечено 5 из 6 кандидатов" in table
    assert "| Точность: записей выпуска с оценкой человека 2-3 | 2 из 3 (67%) |" in table
    assert "| Полнота: «обязательных» по мнению человека в выпуске | 1 из 2 (50%) |" in table
    assert "| Оценка модели совпала с человеком | 3 из 5 (60%) |" in table
    assert "| Приоритет атак и уязвимостей совпал | 1 из 2 (50%) |" in table
    expected_kappa = cohen_kappa_score(
        [3, 2, 2, 1, 0], [3, 2, 1, 3, 0], labels=[0, 1, 2, 3], weights="quadratic"
    )
    assert f"| Взвешенная каппа оценок модели и человека | {expected_kappa:.2f} |" in table


def test_an_empty_file_says_no_data(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    grades = tmp_path / "grades.csv"
    grades.write_text(",".join(evaluation.FIELDS) + "\n", encoding="utf-8")
    evaluation.score(DIGEST, grades)
    table = capsys.readouterr().out

    assert "размечено 0 из" in table
    assert table.count("нет данных") == 6
