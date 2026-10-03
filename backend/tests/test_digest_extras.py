"""What an issue adds beside its entries: the handwork it spares, the plan for a
shift, what changed since earlier issues and management's period in numbers."""

import uuid
from datetime import UTC, date, datetime
from io import BytesIO
from typing import Any

from docx import Document

from radar.digest_extras import (
    VulnerabilityState,
    changes,
    duration_words,
    manual_line,
    manual_work,
    numbers_title,
    period_numbers,
    shift_plan,
    vulnerability_states,
)
from radar.domain import (
    AttackCard,
    Interest,
    ItemSummary,
    ProfileSpec,
    VulnerabilityCard,
    VulnerabilityReference,
)
from radar.render.docx import render_docx
from radar.render.markdown import render_markdown
from radar.views import DigestView, TopicView
from tests.test_render import _item

WEEK = (datetime(2026, 9, 26, tzinfo=UTC), datetime(2026, 10, 3, tzinfo=UTC))


def _digest(audience: str, items: list[Any], stats: dict[str, Any] | None = None) -> DigestView:
    profile = ProfileSpec(
        name="Профиль", interests=(Interest(id="ics", title="АСУ ТП"),), audience=audience
    )
    return DigestView(
        id=uuid.UUID(int=7),
        profile_id=None,
        profile_name=profile.name,
        profile_version=1,
        period_start=WEEK[0],
        period_end=WEEK[1],
        status="done",
        stage="done",
        progress=1.0,
        error=None,
        title="Выпуск",
        stats={"window_total": 377, "selected": 20, "duration_seconds": 4.2, **(stats or {})},
        created_at=WEEK[1],
        finished_at=WEEK[1],
        profile=profile,
        highlights=[],
        topics=[TopicView(title="Уязвимости", overview="", items=items)],
        rejected=[],
    )


def _vulnerability(article_id: int, headline: str, **extra: Any) -> Any:
    return _item(article_id, headline, kind="vulnerability", **extra)


def test_the_handwork_is_counted_by_the_rule_it_states() -> None:
    work = manual_work({"window_total": 377, "selected": 20, "duration_seconds": 4.2})

    assert work is not None
    # 377 headlines at 5 s and 20 entries at 3 min.
    assert work.minutes == 91
    line = manual_line(work)
    assert "377 публикаций и написал 20 записей за 4 с" in line
    assert "около 1,5 ч при 5 с на заголовок и 3 мин на запись" in line
    assert manual_work({"window_total": 0}) is None
    assert [duration_words(minutes) for minutes in (52, 120, 600)] == ["52 мин", "2 ч", "10 ч"]


def test_the_shift_plan_puts_exploited_vulnerabilities_first_with_their_steps() -> None:
    listed = VulnerabilityReference(
        id="CVE-2026-1", kev_added=date(2026, 9, 30), kev_due=date(2026, 10, 21), epss=0.973
    )
    items = [
        _item(
            1,
            "Атака на подстанцию",
            kind="attack",
            priority="high",
            attack=AttackCard(initial_access="фишинг", indicators=("evil[.]com",)),
        ),
        _vulnerability(
            2,
            "Уязвимость без KEV",
            priority="high",
            vulnerability=VulnerabilityCard(fix="Обновить до 2.1", cvss_score="8.1"),
        ),
        _vulnerability(
            3,
            "Уязвимость из KEV",
            priority="high",
            vulnerability=VulnerabilityCard(workaround="Закрыть порт 502", cvss_score="9.8"),
            references=[listed],
        ),
        _vulnerability(4, "Средний приоритет", priority="medium"),
    ]

    plan = shift_plan(items)

    assert [entry.headline for entry in plan] == [
        "Уязвимость из KEV",
        "Уязвимость без KEV",
        "Атака на подстанцию",
    ]
    assert plan[0].steps == ["Временные меры: Закрыть порт 502"]
    assert plan[0].facts == [
        "в каталоге CISA KEV с 30.09.2026, устранить до 21.10.2026",
        "EPSS 97,3%",
        "CVSS 9.8",
    ]
    assert plan[2].steps == [
        "Проверить первоначальный доступ: фишинг",
        "Поискать индикаторы: evil[.]com",
    ]


def _state(**extra: Any) -> VulnerabilityState:
    fields = {
        "id": "CVE-2026-1",
        "headline": "FortiMail",
        "url": "https://example.org/1",
        "day": date(2026, 9, 30),
        "exploit": "unknown",
    }
    return VulnerabilityState.model_validate({**fields, **extra})


def test_a_known_vulnerability_reports_the_catalogue_the_exploit_and_the_update() -> None:
    earlier = {"CVE-2026-1": _state()}
    now = {
        "CVE-2026-1": _state(
            day=date(2026, 10, 2), exploit="in_the_wild", kev_added=date(2026, 10, 1), fixed=True
        ),
        "CVE-2026-2": _state(id="CVE-2026-2", kev_added=date(2026, 10, 1)),
    }

    [change] = changes(earlier, now)

    assert change.id == "CVE-2026-1"
    assert change.since == date(2026, 9, 30)
    assert change.what == [
        "попала в каталог CISA KEV 01.10.2026",
        "эксплойт: было «нет данных», стало «используется в атаках»",
        "вышло обновление или мера устранения",
    ]
    # Nothing new is nothing to report.
    assert changes(now, now) == []


def test_the_latest_issue_decides_what_was_known() -> None:
    old = ItemSummary(
        summary="",
        vulnerability=VulnerabilityCard(ids=("CVE-2026-1",), exploit="none"),
    )
    newer = ItemSummary(
        summary="",
        vulnerability=VulnerabilityCard(ids=("CVE-2026-1",), exploit="public"),
        references=(VulnerabilityReference(id="CVE-2026-1", kev_added=date(2026, 9, 29)),),
    )

    states = vulnerability_states(
        [
            (newer, "Новее", "https://example.org/2", datetime(2026, 9, 30, tzinfo=UTC)),
            (old, "Старее", "https://example.org/1", datetime(2026, 9, 20, tzinfo=UTC)),
        ]
    )

    assert states["CVE-2026-1"].headline == "Новее"
    assert states["CVE-2026-1"].exploit == "public"
    assert states["CVE-2026-1"].kev_added == date(2026, 9, 29)


def test_managements_numbers_count_the_tags_beside_the_previous_issue() -> None:
    items = [
        _item(1, "Атака на ТЭЦ", tags=["ru", "energy"]),
        _item(2, "Утечка", tags=["ru", "data_leak"]),
    ]

    rows = period_numbers(items, {"ru": 1, "industry": 2})

    assert [(row.label, row.count, row.before) for row in rows] == [
        ("В РФ", 2, 1),
        ("Энергетика", 1, 0),
        ("Утечка чувствительной информации", 1, 0),
        ("Промышленность", 0, 2),
    ]
    assert numbers_title(*WEEK) == "Неделя в цифрах"


def test_a_specialists_issue_shows_the_plan_and_the_changes_in_markdown_and_docx() -> None:
    change = {
        "id": "CVE-2026-1",
        "headline": "FortiMail",
        "url": "https://example.org/1",
        "since": "2026-09-30",
        "what": ["попала в каталог CISA KEV 01.10.2026"],
    }
    digest = _digest(
        "specialist",
        [
            _vulnerability(
                1,
                "FortiMail [запись файлов]",
                priority="high",
                vulnerability=VulnerabilityCard(fix="Обновить до 7.4.9"),
            )
        ],
        {"changes": [change]},
    )

    markdown = render_markdown(digest)
    document = Document(BytesIO(render_docx(digest)))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert "*Вместо ручной работы: ассистент просмотрел 377 публикаций" in markdown
    assert "## План на смену\n\n- [ ] [FortiMail \\[запись файлов\\]](https://example.org/a/1)" in (
        markdown
    )
    assert "  - Обновление: Обновить до 7.4.9" in markdown
    assert "- **CVE-2026-1**, [FortiMail](https://example.org/1): попала в каталог CISA KEV" in (
        markdown
    )
    assert "manual_minutes: 91" in markdown
    for heading in ("План на смену", "Что изменилось с прошлых выпусков", "Вместо ручной работы"):
        assert heading in text


def test_managements_issue_shows_its_period_in_numbers_and_no_plan() -> None:
    digest = _digest(
        "management",
        [_item(1, "Атака на ТЭЦ", priority="high", kind="attack", tags=["ru", "energy"])],
        {"tags_before": {"ru": 3}},
    )

    markdown = render_markdown(digest)

    assert digest.plan == []
    assert "## Неделя в цифрах" in markdown
    assert "| В РФ | 1 | 3 |" in markdown
    assert "План на смену" not in markdown
