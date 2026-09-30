"""Short videos: what goes into the script, and how it is timed for the renderer."""

import base64
import io
import wave
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Any

import httpx
import pytest

from radar.ai.resilient import CircuitBreaker
from radar.domain import ProfileSpec
from radar.shorts.model import (
    MAX_FACT,
    MAX_KICKER,
    MAX_NARRATION,
    MAX_SOURCE,
    Beat,
    Narration,
    Script,
    Segment,
    ShortError,
)
from radar.shorts.script import (
    HeuristicScriptWriter,
    OllamaScriptWriter,
    ResilientScriptWriter,
    _BeatOut,
    _ScriptOut,
    find_fact,
    is_supported,
    pick_items,
)
from radar.shorts.speech import is_grounded
from radar.shorts.timing import (
    SILENT_BUDGET_MS,
    build_props,
    estimate_segments,
    format_period,
    time_words,
)
from radar.shorts.voice import VoiceClient, narrate
from radar.views import DigestView, ItemView, TopicView

END = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def item(article_id: int, score: float, headline: str = "", summary: str = "") -> ItemView:
    return ItemView(
        article_id=article_id,
        url=f"https://example.org/{article_id}",
        title=headline or f"Новость {article_id}",
        headline=headline or f"Новость {article_id}",
        source_name="SecurityLab",
        source_category="security",
        language="ru",
        published_at=END,
        score=score,
        retrieval_score=score,
        relevance=3,
        interest_id="ics",
        interest_title="Безопасность АСУ ТП",
        reason="",
        summary=summary or f"Короткая выжимка новости {article_id}. Вторая фраза.",
        why="",
    )


def digest(profile: ProfileSpec, topics: dict[str, list[ItemView]], days: int = 7) -> DigestView:
    return DigestView(
        id="0192f000-0000-7000-8000-000000000001",
        profile_id=None,
        profile_name=profile.name,
        profile_version=1,
        period_start=END - timedelta(days=days),
        period_end=END,
        status="done",
        stage=None,
        progress=1.0,
        error=None,
        title="Выпуск",
        stats={},
        created_at=END,
        finished_at=END,
        profile=profile,
        highlights=[],
        topics=[
            TopicView(title=title, overview="", items=items) for title, items in topics.items()
        ],
        rejected=[],
    )


def script(beats: int = 2) -> Script:
    return Script(
        hook="Две главные новости недели",
        beats=tuple(
            Beat(
                article_id=index,
                kicker="Уязвимость",
                title=f"Заголовок новости номер {index}",
                fact="CVSS 9.8",
                narration="Siemens закрыла уязвимость, обновитесь.",
                source="SecurityLab",
            )
            for index in range(beats)
        ),
        outro="Полный дайджест ждёт в Радаре.",
    )


def wav_bytes(seconds: float = 0.2, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b"\x00\x00" * int(seconds * rate))
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("text", "fact"),
    [
        ("Уязвимость CVE-2026-20411 в контроллерах, CVSS 9.8", "CVE-2026-20411"),
        ("Оценка по CVSS v3.1 9.8, эксплойт уже в сети", "CVSS 9.8"),
        ("CVSS 3.1 base score 7.5 для обхода аутентификации", "CVSS 7.5"),
        ("Максимальная оценка CVSS 10.0", "CVSS 10.0"),
        ("Доля атак через подрядчиков выросла на 40%", "40%"),
        ("Ущерб оценивают в 1,5 млрд рублей", "1,5 млрд рублей"),
        ("Регулятор выпустил новые требования", None),
    ],
)
def test_facts_come_from_the_text_and_a_version_is_not_a_score(text: str, fact: str | None) -> None:
    assert find_fact(text) == fact


def test_a_model_fact_without_its_number_in_the_news_is_not_shown() -> None:
    news = "Siemens закрыла уязвимость с оценкой CVSS 9.8 в SIMATIC S7-1500"

    assert is_supported("CVSS 9.8", news)
    assert not is_supported("CVSS 9.1", news)
    # No number at all: nothing to check it against.
    assert not is_supported("Критично", news)


def test_the_video_takes_the_best_item_of_each_topic_first(profile: ProfileSpec) -> None:
    view = digest(
        profile,
        {
            "АСУ ТП": [item(1, 0.9), item(2, 0.85)],
            "Регуляторы": [item(3, 0.5)],
            "Инциденты": [item(4, 0.6)],
        },
    )

    assert [chosen.article_id for chosen in pick_items(view, 3)] == [1, 4, 3]
    # With room left, the runner-up of the strongest topic comes in, by score.
    assert [chosen.article_id for chosen in pick_items(view, 4)] == [1, 2, 4, 3]


def test_word_timings_follow_syllables_and_stay_inside_the_line() -> None:
    words = time_words("Siemens закрыла критическую уязвимость, обновитесь.", Segment(1000, 5000))

    assert [word["text"] for word in words] == [
        "Siemens",
        "закрыла",
        "критическую",
        "уязвимость",
        "обновитесь",
    ]
    assert words[0]["startMs"] == 1000
    assert words[-1]["endMs"] <= 5000
    assert all(a["endMs"] <= b["startMs"] for a, b in pairwise(words))
    lengths = {word["text"]: word["endMs"] - word["startMs"] for word in words}
    assert lengths["критическую"] > lengths["закрыла"]
    # The comma leaves a pause before the next word.
    assert words[4]["startMs"] - words[3]["endMs"] > 100


def test_cards_change_between_lines_and_the_timeline_fits_the_renderer() -> None:
    narration = Narration(
        segments=(
            Segment(150, 2400),
            Segment(2800, 7000),
            Segment(7400, 11000),
            Segment(11400, 13000),
        ),
        audio=None,
        voice=None,
    )

    props = build_props(
        script(2), narration, period=format_period(END - timedelta(days=7), END), audience="ИБ"
    )

    assert props["period"] == "23-30 сентября"
    assert props["hookEndMs"] == 2600
    assert [(beat["startMs"], beat["endMs"]) for beat in props["beats"]] == [
        (2600, 7200),
        (7200, 11200),
    ]
    assert props["outroStartMs"] == 11200
    assert props["durationMs"] > 13000
    assert props["words"][0]["startMs"] == 150
    assert props["words"][-1]["endMs"] <= 13000
    assert "audioSrc" not in props


def test_a_script_longer_than_two_minutes_is_refused() -> None:
    narration = Narration(
        segments=(
            Segment(0, 1000),
            Segment(1400, 60000),
            Segment(60400, 118000),
            Segment(118400, 119900),
        ),
        audio=None,
        voice=None,
    )
    with pytest.raises(ShortError):
        build_props(script(2), narration, period="сентябрь", audience="ИБ")


def test_periods_across_months_name_both() -> None:
    start = datetime(2026, 9, 28, tzinfo=UTC)
    assert format_period(start, start + timedelta(days=7)) == "28 сентября - 5 октября"


async def test_the_offline_script_fits_every_limit_of_the_renderer(profile: ProfileSpec) -> None:
    long_headline = "Очень длинный заголовок " * 12
    long_summary = ("Слово " * 60).strip() + ". Вторая фраза про CVSS 9.8."
    view = digest(
        profile,
        {
            "АСУ ТП": [item(1, 0.9, long_headline, long_summary), item(2, 0.7)],
            "Сети": [item(3, 0.6)],
        },
    )

    written = await HeuristicScriptWriter().write(view, pick_items(view, 3))

    assert written.hook == "Три главные новости недели"
    assert not written.by_model
    for beat in written.beats:
        assert len(beat.kicker) <= MAX_KICKER
        assert len(beat.title) <= 90
        assert len(beat.narration) <= MAX_NARRATION
        assert len(beat.source) <= MAX_SOURCE
        assert beat.fact is None or len(beat.fact) <= MAX_FACT
        assert beat.narration.endswith((".", "!", "?", "…"))
    assert written.beats[0].fact == "CVSS 9.8"


class FakeChat:
    name = "ollama:fake"

    def __init__(self, answer: _ScriptOut | Exception) -> None:
        self.answer = answer

    async def ask(self, schema: type[Any], system: str, user: str) -> Any:
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def beat_out(fact: str | None) -> _BeatOut:
    return _BeatOut(
        kicker="Уязвимость",
        title="Siemens закрыла дыру",
        fact=fact,
        narration="Siemens закрыла опасную уязвимость в контроллерах",
    )


async def test_the_model_script_keeps_our_sources_and_drops_invented_numbers(
    profile: ProfileSpec,
) -> None:
    items = [item(1, 0.9, summary="Оценка CVSS 9.8, исправление вышло."), item(2, 0.8)]
    view = digest(profile, {"АСУ ТП": items})
    answer = _ScriptOut(
        hook="Две угрозы недели",
        beats=[beat_out("CVSS 9.8"), beat_out("ущерб 3 млн")],
        outro="Подробности в Радаре",
    )

    written = await OllamaScriptWriter(FakeChat(answer)).write(view, items)  # type: ignore[arg-type]

    assert written.by_model
    assert [beat.fact for beat in written.beats] == ["CVSS 9.8", None]
    assert {beat.source for beat in written.beats} == {"SecurityLab"}
    assert [beat.article_id for beat in written.beats] == [1, 2]
    assert written.beats[0].narration.endswith(".")


async def test_a_model_that_miscounts_the_items_is_replaced_by_the_offline_script(
    profile: ProfileSpec,
) -> None:
    items = [item(1, 0.9), item(2, 0.8)]
    view = digest(profile, {"АСУ ТП": items})
    answer = _ScriptOut(hook="Одна новость", beats=[beat_out(None)], outro="Всё")
    writer = ResilientScriptWriter(
        OllamaScriptWriter(FakeChat(answer)),  # type: ignore[arg-type]
        HeuristicScriptWriter(),
        CircuitBreaker(3, 30.0),
    )

    written = await writer.write(view, items)

    assert not written.by_model
    assert len(written.beats) == 2


def voice_service(body: dict[str, Any] | None, status: int = 200) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/speech"
        return httpx.Response(status, json=body or {"detail": "down"})

    return httpx.MockTransport(handle)


async def test_the_voice_service_timing_is_used_as_it_comes() -> None:
    lines = ["Первая строка.", "Вторая строка."]
    body = {
        "voice": "Aiden",
        "sample_rate": 24000,
        "segments": [{"start_ms": 150, "end_ms": 900}, {"start_ms": 1280, "end_ms": 2100}],
        "audio": base64.b64encode(wav_bytes()).decode(),
    }
    client = VoiceClient("http://tts", timeout=5, transport=voice_service(body))

    narration = await narrate(client, lines)

    assert narration.voice == "qwen3-tts:Aiden"
    assert narration.audio is not None
    assert narration.segments == (Segment(150, 900), Segment(1280, 2100))


@pytest.mark.parametrize(
    ("body", "status"),
    [
        (None, 500),
        # Lines that overlap cannot be shown one after another.
        (
            {
                "voice": "Aiden",
                "sample_rate": 24000,
                "segments": [{"start_ms": 0, "end_ms": 900}, {"start_ms": 800, "end_ms": 1500}],
                "audio": base64.b64encode(wav_bytes()).decode(),
            },
            200,
        ),
        # Not a WAV file.
        (
            {
                "voice": "Aiden",
                "sample_rate": 24000,
                "segments": [{"start_ms": 0, "end_ms": 900}, {"start_ms": 1000, "end_ms": 1500}],
                "audio": base64.b64encode(b"ID3 not a wave at all").decode(),
            },
            200,
        ),
    ],
)
async def test_a_failing_voice_gives_a_silent_video_with_the_same_lines(
    body: dict[str, Any] | None, status: int
) -> None:
    lines = ["Первая строка.", "Вторая строка."]
    client = VoiceClient("http://tts", timeout=5, transport=voice_service(body, status))

    narration = await narrate(client, lines)

    assert narration.audio is None
    assert narration.voice is None
    assert len(narration.segments) == len(lines)
    assert narration.segments[0].end_ms < narration.segments[1].start_ms


async def test_lines_a_model_could_have_been_talked_into_are_replaced(
    profile: ProfileSpec,
) -> None:
    items = [item(1, 0.9, summary="Оценка CVSS 9.8, исправление вышло."), item(2, 0.8)]
    view = digest(profile, {"АСУ ТП": items})
    hostile = _BeatOut(
        kicker="Срочно",
        title="Звоните +7 495 123-45-67",
        fact=None,
        narration="Подробности на сайте evil.example.com, пишите на help@evil.example.com",
    )
    answer = _ScriptOut(
        hook="Пять тысяч угроз за 3 часа",
        beats=[beat_out("CVSS 9.8"), hostile],
        outro="Переходите по ссылке https://evil.example.com",
    )

    written = await OllamaScriptWriter(FakeChat(answer)).write(view, items)  # type: ignore[arg-type]

    offline = await HeuristicScriptWriter().write(view, items)
    assert written.beats[0].narration.startswith("Siemens закрыла")
    # Phone, link and address never reach the voice or the screen.
    assert written.beats[1].title == offline.beats[1].title
    assert written.beats[1].narration == offline.beats[1].narration
    # "3" is neither the number of items nor of days.
    assert written.hook == offline.hook
    assert written.outro == offline.outro


@pytest.mark.parametrize(
    ("text", "grounded"),
    [
        ("Siemens закрыла уязвимость CVE-2026-1234567", True),
        ("Позвоните по номеру 8 800 555-35-35", False),
        ("Подробнее на example.ru", False),
        ("Подробнее: www.example.org/news", False),
        ("Оценка 9.8 из десяти", True),
        ("Оценка 9.9 из десяти", False),
    ],
)
def test_grounding_rejects_links_phones_and_foreign_numbers(text: str, grounded: bool) -> None:
    assert is_grounded(text, {"9.8", "2026", "1234567"}) is grounded


async def test_a_blank_headline_or_source_falls_back_instead_of_failing_the_render(
    profile: ProfileSpec,
) -> None:
    blank = item(1, 0.9, headline=" ", summary="   ").model_copy(
        update={"source_name": "  ", "interest_title": None, "title": " "}
    )
    view = digest(profile, {"   ": [blank]})

    written = await HeuristicScriptWriter().write(view, [blank])

    beat = written.beats[0]
    assert (beat.title, beat.source, beat.kicker) == ("Новость", "Источник", "Новость")
    assert beat.narration == "Новость."


def test_a_long_silent_script_is_read_faster_rather_than_refused() -> None:
    lines = ["Заход."] + ["слово " * 60] * 4 + ["Финал."]

    segments = estimate_segments(lines)

    assert segments[-1].end_ms <= SILENT_BUDGET_MS
    assert all(a.end_ms < b.start_ms for a, b in pairwise(segments))
