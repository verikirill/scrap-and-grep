"""What a `radar digest` command line asks for."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from radar.console import Audience, ConsoleError, Target, file_stem, progress_line, targets
from radar.seed import DEFAULT_PROFILES


def test_without_options_both_audiences_come_with_their_own_period() -> None:
    wanted = targets(None, None, None, None)

    assert [(t.label, t.profile_name) for t in wanted] == [
        ("specialist", "Специалист по ИБ АСУ ТП"),
        ("management", "Руководство и сотрудники: кибербезопасность"),
    ]
    # Specialists read daily and management weekly, as the jury asked.
    assert [t.period(t.label) for t in wanted] == [1, 7]  # type: ignore[arg-type]


def test_the_example_profiles_named_here_exist_in_the_seed() -> None:
    seeded = {spec.name: spec.audience for spec in DEFAULT_PROFILES}

    for target in targets(Audience.both, None, None, None):
        assert seeded[target.profile_name or ""] == target.label


def test_an_explicit_period_wins_over_the_audience() -> None:
    (target,) = targets(Audience.management, None, None, 30)

    assert target.label == "management"
    assert target.period("management") == 30


def test_a_profile_file_is_read_and_named_after_the_file(tmp_path: Path) -> None:
    spec = next(p for p in DEFAULT_PROFILES if p.audience == "management")
    path = tmp_path / "board.json"
    path.write_text(spec.model_dump_json(), encoding="utf-8")

    (target,) = targets(None, None, path, None)

    assert target == Target(label="board", spec=spec)
    assert target.period(spec.audience) == 7


@pytest.mark.parametrize(
    "content",
    ["not json", json.dumps({"name": "x"})],
    ids=["broken", "no interests"],
)
def test_a_bad_profile_file_is_told_in_words(tmp_path: Path, content: str) -> None:
    path = tmp_path / "profile.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConsoleError, match=r"profile\.json"):
        targets(None, None, path, None)


def test_two_ways_of_choosing_a_profile_at_once_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ConsoleError, match="что-то одно"):
        targets(Audience.specialist, "Мой профиль", None, None)


def test_files_say_who_they_are_for_and_the_period() -> None:
    built = datetime(2026, 10, 3, 9, 30, tzinfo=UTC)

    assert file_stem("specialist", 1, built) == "specialist-1d-20261003-0930"
    assert progress_line("grade", 0.42) == " 42%  Оцениваем релевантность"
