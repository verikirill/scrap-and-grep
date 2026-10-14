"""What a `radar digest` command line asks for."""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from radar import cli
from radar.console import (
    Audience,
    ConsoleError,
    Target,
    addresses,
    file_stem,
    moment,
    progress_line,
    targets,
)
from radar.domain import Audience as ProfileAudience
from radar.ingest import telegram
from radar.ingest.detect import Found, as_source
from radar.seed import DEFAULT_PROFILES

# The console examples in examples/ were built on 3 October at 04:27 Moscow time.
EXAMPLES_BUILT = datetime(2026, 10, 3, 1, 27, tzinfo=UTC)
NOW = datetime(2026, 10, 14, 18, 0, tzinfo=UTC)

Run = Callable[..., Result]


@pytest.fixture
def command_line(monkeypatch: pytest.MonkeyPatch) -> Run:
    """`radar digest` with these options, as a terminal would run it."""
    # The command sets up logging for the whole process. Set up inside the
    # runner, it sends the later tests' log lines to the runner's closed output,
    # and they fail on the write.
    monkeypatch.setattr(cli, "configure_logging", lambda *_, **__: None)

    def run(*options: str) -> Result:
        return CliRunner().invoke(cli.app, ["digest", *options])

    return run


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


@pytest.mark.parametrize(
    "text",
    ["2026-10-03T04:27", "2026-10-03T04:27+03:00", "2026-10-03T01:27Z"],
    ids=["no offset", "moscow offset", "utc"],
)
def test_a_date_and_time_without_an_offset_is_moscow_time(text: str) -> None:
    # The digests say МСК, so a time typed as it stands there means the same.
    assert moment(text) == EXAMPLES_BUILT


def test_a_date_and_time_not_in_iso_8601_is_told_in_words(command_line: Run) -> None:
    result = command_line("--period-end", "03.10.2026 04:27")

    assert result.exit_code == 2
    # An example of the format, not only the value given back.
    assert "2026-10-03T04:27" in result.output


@pytest.mark.parametrize(
    ("audience", "days", "back"),
    [("specialist", None, 1), ("management", None, 7), ("management", 30, 30)],
    ids=["a day for specialists", "a week for management", "an explicit month"],
)
def test_a_fixed_end_counts_the_period_back_from_it(
    audience: ProfileAudience, days: int | None, back: int
) -> None:
    (target,) = targets(Audience(audience), None, None, days, end=EXAMPLES_BUILT, now=NOW)

    assert target.bounds(audience, NOW) == (EXAMPLES_BUILT - timedelta(days=back), EXAMPLES_BUILT)


def test_a_period_without_a_fixed_end_runs_until_now() -> None:
    (daily,) = targets(Audience.specialist, None, None, None, now=NOW)
    (since,) = targets(Audience.specialist, None, None, None, start=EXAMPLES_BUILT, now=NOW)

    assert daily.bounds("specialist", NOW) == (NOW - timedelta(days=1), NOW)
    assert since.bounds("specialist", NOW) == (EXAMPLES_BUILT, NOW)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (EXAMPLES_BUILT, EXAMPLES_BUILT - timedelta(days=1)),
        (EXAMPLES_BUILT, EXAMPLES_BUILT),
        (NOW + timedelta(hours=1), None),
    ],
    ids=["reversed", "empty", "starting after now"],
)
def test_a_period_must_start_before_it_ends(start: datetime, end: datetime | None) -> None:
    with pytest.raises(ConsoleError, match="раньше конца"):
        targets(Audience.specialist, None, None, None, start=start, end=end, now=NOW)


def test_days_and_a_fixed_start_at_once_are_refused() -> None:
    # With the start fixed the days would count nothing and be quietly dropped.
    with pytest.raises(ConsoleError, match="что-то одно"):
        targets(Audience.specialist, None, None, 3, start=EXAMPLES_BUILT, now=NOW)


def test_the_command_line_builds_the_period_it_fixes(
    command_line: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: list[Target] = []

    async def build(target: Target, *_: object) -> Path:
        built.append(target)
        return Path("specialist.md")

    monkeypatch.setattr(cli, "_build", build)
    result = command_line("--audience", "specialist", "--period-end", "2026-10-03T04:27")

    assert result.exit_code == 0, result.output
    (target,) = built
    assert target.bounds("specialist", NOW) == (EXAMPLES_BUILT - timedelta(days=1), EXAMPLES_BUILT)


def test_files_say_who_they_are_for_and_the_period() -> None:
    built = datetime(2026, 10, 3, 9, 30, tzinfo=UTC)

    def stem(label: str, length: timedelta) -> str:
        return file_stem(label, built - length, built, built)

    assert stem("specialist", timedelta(days=1)) == "specialist-1d-20261003-0930"
    # A fixed period counts in whole days: the week of scripts/make_examples.py,
    # 25.09 00:00 - 02.10 16:00, makes eight, and two hours still make one.
    assert stem("management", timedelta(days=7, hours=16)) == "management-8d-20261003-0930"
    assert stem("specialist", timedelta(hours=2)) == "specialist-1d-20261003-0930"
    assert progress_line("grade", 0.42) == " 42%  Оцениваем релевантность"


def test_a_sources_file_skips_comments_blank_lines_and_repeats() -> None:
    text = "\n".join(
        [
            "# сайты вне датасета",
            "https://www.securitycode.ru/company/news/",
            "",
            "@dataleak",
            "  https://www.securitycode.ru/company/news/  ",
        ]
    )

    assert addresses(text) == ["https://www.securitycode.ru/company/news/", "@dataleak"]


def test_a_detected_address_becomes_the_row_the_form_would_add() -> None:
    channel = as_source(
        Found(kind="telegram", address="dataleak", name="Утечки", site_url=None, language="ru")
    )
    page = as_source(
        Found(
            kind="page",
            address="https://example.org/news",
            name="",
            site_url="https://example.org",
            language="en",
            link_selector="article h2 a",
        )
    )

    assert (channel.slug, channel.feed_url, channel.fetch_full_text) == (
        "tg-dataleak",
        telegram.feed_url("dataleak"),
        True,
    )
    assert page.slug.startswith("custom-")
    assert (page.name, page.kind, page.language, page.link_selector) == (
        "https://example.org/news",
        "page",
        "en",
        "article h2 a",
    )
