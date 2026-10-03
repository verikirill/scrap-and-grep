"""The spoken brief of a management digest: its script, its voice and its API."""

import base64
import io
import json
import uuid
import wave
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from radar.briefing import service
from radar.briefing.script import (
    MAX_MS,
    MS_PER_SYLLABLE,
    OUTRO,
    BriefingError,
    build_script,
    estimate_ms,
)
from radar.domain import Interest, ProfileSpec
from radar.shorts.voice import VoiceClient
from radar.views import DigestView, ItemView, TopicView
from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    api,
    database,
    finished_digest,
    register,
    seed_articles,
)

END = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)
# The voice service takes a sentence of 400 characters at most.
VOICE_LINE_LIMIT = 400


def entry(article_id: int, score: float, headline: str, why: str = "") -> ItemView:
    return ItemView(
        article_id=article_id,
        url=f"https://example.org/{article_id}",
        title=headline,
        headline=headline,
        source_name="SecurityLab",
        source_category="security",
        language="ru",
        published_at=END,
        score=score,
        retrieval_score=score,
        relevance=3,
        interest_id="risk",
        interest_title="Риски",
        reason="",
        summary="Короткая выжимка. Вторая фраза выжимки.",
        why=why,
    )


def management(
    items: list[ItemView],
    *,
    implications: tuple[str, ...] = (),
    highlights: tuple[str, ...] = (),
    title: str = "Массовые уязвимости в промышленном ПО",
) -> DigestView:
    profile = ProfileSpec(
        name="Руководство", interests=(Interest(id="risk", title="Риски"),), audience="management"
    )
    return DigestView(
        id="0192f000-0000-7000-8000-000000000001",
        profile_id=None,
        profile_name=profile.name,
        profile_version=1,
        audience="management",
        period_start=END - timedelta(days=7),
        period_end=END,
        status="done",
        stage=None,
        progress=1.0,
        error=None,
        title=title,
        stats={},
        created_at=END,
        finished_at=END,
        profile=profile,
        highlights=list(highlights),
        implications=list(implications),
        topics=[TopicView(title="Уязвимости", overview="", items=items)],
        rejected=[],
    )


# Texts of a management digest of the stand, as the model wrote them.
CODESYS = entry(
    1,
    1.0,
    "Две уязвимости в CODESYS позволяют вызвать отказ в обслуживании",
    "Без установки патчей контроллеры могут выйти из строя, что нарушит работу подстанций.",
)
FSTEC = entry(
    2,
    0.95,
    "ФСТЭК разъяснила сроки представления результатов оценки защищённости",
    "Компания должна сдавать отчёты в течение пяти рабочих дней, иначе получит замечания.",
)
ABB = entry(
    3,
    0.88,
    "В ABB PCM600 можно повысить привилегии и записать файлы вне каталога",
    "Это открывает путь к подмене настроек релейной защиты на подстанциях.",
)
IMPLICATIONS = (
    "Риск: сбои в системах управления подстанциями - нужно срочно поставить патчи.",
    "Действие: проверить соответствие требованиям ФСТЭК в кратчайшие сроки.",
)
HIGHLIGHTS = (
    "В CODESYS нашли две уязвимости, способные вывести системы из строя.",
    "Fortinet сообщает об активной эксплуатации уязвимости в FortiMail.",
)


def test_the_brief_tells_the_title_what_it_means_the_highlights_and_the_entries() -> None:
    view = management([ABB, CODESYS, FSTEC], implications=IMPLICATIONS, highlights=HIGHLIGHTS)

    lines = build_script(view).lines

    assert lines[0] == (
        "Брифинг Tail and Grep для руководства, 26 сентября - 3 октября. "
        "Массовые уязвимости в промышленном ПО."
    )
    assert lines[1] == f"Что это значит для нас. {IMPLICATIONS[0]}"
    assert lines[2] == IMPLICATIONS[1]
    assert lines[3] == f"Главное. {HIGHLIGHTS[0]}"
    assert lines[4] == HIGHLIGHTS[1]
    # The strongest entries first, each with what it means for the company.
    assert lines[5] == f"Подробнее о главных событиях. {CODESYS.headline}. {CODESYS.why}"
    assert lines[6] == f"{FSTEC.headline}. {FSTEC.why}"
    assert lines[7] == f"{ABB.headline}. {ABB.why}"
    assert lines[8] == OUTRO


def test_an_entry_without_a_word_on_the_company_is_told_by_its_summary() -> None:
    quiet = entry(4, 0.9, "Утечка данных у подрядчика")

    text = "\n".join(build_script(management([quiet, CODESYS, FSTEC])).lines)

    assert "\nУтечка данных у подрядчика. Короткая выжимка.\n" in text


@pytest.mark.parametrize(
    "mark",
    [
        pytest.param("CVE-2026-76504", id="cve"),
        pytest.param("BDU:2026-15713", id="bdu"),
        pytest.param("CVSS 9.8", id="cvss-score"),
        pytest.param("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", id="cvss-vector"),
        pytest.param("185.220.101.4", id="ipv4"),
        pytest.param("185.220.101[.]4", id="ipv4-defanged"),
        pytest.param("2001:db8:85a3::8a2e:370:7334", id="ipv6"),
        pytest.param("d41d8cd98f00b204e9800998ecf8427e", id="md5"),
        pytest.param(
            "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", id="sha256"
        ),
        pytest.param("https://example.org/advisory/7", id="link"),
        pytest.param("update-check[.]example[.]com", id="domain"),
        pytest.param("T1566.001", id="attack-technique"),
        pytest.param("CWE-79", id="cwe"),
    ],
)
def test_the_brief_carries_no_technical_marks(mark: str) -> None:
    marked = entry(
        5, 1.0, f"Cisco закрыла уязвимость {mark}", f"Обновите шлюзы ({mark}), это займёт день."
    )
    view = management(
        [marked, CODESYS, FSTEC],
        implications=(f"Риск: взлом шлюзов через {mark}.",),
        highlights=(f"Cisco выпустила патч, {mark}.",),
        title=f"Уязвимость {mark} в шлюзах",
    )

    text = "\n".join(build_script(view).lines)

    assert mark not in text
    # The words around the mark stay, with no empty brackets or stray commas.
    assert "Cisco закрыла уязвимость. Обновите шлюзы, это займёт день." in text
    assert "Риск: взлом шлюзов через." in text
    assert "()" not in text
    assert " ," not in text


def test_ordinary_numbers_stay_in_the_brief() -> None:
    plain_numbers = entry(
        6, 1.0, "Atlassian закрыла уязвимости в версии 9.12", "Доля атак выросла на 40% за 3 дня."
    )

    text = "\n".join(build_script(management([plain_numbers, CODESYS, FSTEC])).lines)

    assert "версии 9.12" in text
    assert "на 40% за 3 дня" in text


def long_text(words: int, seed: str) -> str:
    return " ".join(f"{seed}{index}" for index in range(words)) + "."


def test_a_long_digest_fits_two_minutes_and_keeps_three_entries() -> None:
    items = [
        entry(10 + index, 1.0 - index / 20, long_text(20, "заголовок"), long_text(45, "смысл"))
        for index in range(10)
    ]
    view = management(
        items,
        implications=tuple(long_text(45, "риск") for _ in range(3)),
        highlights=tuple(long_text(45, "главное") for _ in range(5)),
    )

    script = build_script(view)

    assert script.estimated_ms == estimate_ms(script.lines)
    assert script.estimated_ms <= MAX_MS
    assert 3 <= script.entries <= 5
    assert max(len(line) for line in script.lines) <= VOICE_LINE_LIMIT


def test_a_short_digest_keeps_five_entries_three_risks_and_three_highlights() -> None:
    items = [
        entry(20 + index, 1.0 - index / 20, f"Новость {index}", "Важно.") for index in range(7)
    ]
    view = management(
        items,
        implications=("Риск один.", "Риск два.", "Риск три.", "Риск четыре."),
        highlights=("Главное один.", "Главное два.", "Главное три.", "Главное четыре."),
    )

    script = build_script(view)

    assert script.entries == 5
    assert sum("Риск" in line for line in script.lines) == 3
    assert sum("Главное " in line for line in script.lines) == 3


def test_the_length_is_counted_in_syllables_at_the_pace_of_the_voice() -> None:
    assert estimate_ms(["Раз два три."]) == 3 * MS_PER_SYLLABLE
    assert estimate_ms(["Раз два три.", "Раз."]) > estimate_ms(["Раз два три."]) + MS_PER_SYLLABLE


def test_a_digest_without_entries_has_no_brief() -> None:
    with pytest.raises(BriefingError):
        build_script(management([], implications=IMPLICATIONS, highlights=HIGHLIGHTS))


RATE = 24000


def wav_bytes(seconds: float, level: int = 0) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(level.to_bytes(2, "little", signed=True) * int(seconds * RATE))
    return buffer.getvalue()


def test_the_parts_of_the_voice_join_into_one_wav_with_a_pause_between() -> None:
    joined = service.join_wav([wav_bytes(1.0, 100), wav_bytes(0.5, 200)], gap_ms=400)

    with wave.open(io.BytesIO(joined), "rb") as reader:
        frames = reader.readframes(reader.getnframes())
    samples = [int.from_bytes(frames[i : i + 2], "little", signed=True) for i in (0, 2 * RATE)]
    assert service.duration_ms(joined) == 1900
    # The first part, then silence where the pause is, then the second part.
    assert samples == [100, 0]
    assert frames[-2:] == (200).to_bytes(2, "little", signed=True)


def test_parts_in_different_formats_are_not_joined() -> None:
    other = io.BytesIO()
    with wave.open(other, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\x00\x00" * 1600)

    with pytest.raises(ValueError, match="formats"):
        service.join_wav([wav_bytes(0.1), other.getvalue()], gap_ms=400)


def voice_service(seen: list[dict[str, object]], refuse: str | None = None) -> httpx.MockTransport:
    """The voice service: a second of sound per sentence, a 400 for a voice it lost."""

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if refuse is not None and body["voice"] == refuse:
            return httpx.Response(400, json={"detail": "unknown speaker"})
        count = len(body["sentences"])
        return httpx.Response(
            200,
            json={
                "voice": body["voice"] or "anchor",
                "sample_rate": RATE,
                "segments": [
                    {"start_ms": index * 1000, "end_ms": index * 1000 + 900}
                    for index in range(count)
                ],
                "audio": base64.b64encode(wav_bytes(float(count))).decode(),
            },
        )

    return httpx.MockTransport(handle)


async def test_a_brief_is_voiced_a_few_lines_at_a_time_and_reports_each_part() -> None:
    seen: list[dict[str, object]] = []
    client = VoiceClient("http://tts", timeout=5, transport=voice_service(seen))
    parts: list[tuple[int, int]] = []

    async def on_part(done: int, total: int) -> None:
        parts.append((done, total))

    lines = [f"Строка номер {index}." for index in range(9)]
    audio, voice = await service.speak(client, lines, "presenter", on_part)

    assert [len(body["sentences"]) for body in seen] == [4, 4, 1]  # type: ignore[arg-type]
    assert [body["voice"] for body in seen] == ["presenter"] * 3
    assert parts == [(1, 3), (2, 3), (3, 3)]
    assert voice == "qwen3-tts:presenter"
    # Nine seconds of voice and two pauses between the three parts.
    assert service.duration_ms(audio) == 9000 + 2 * 380


async def test_a_voice_the_service_lost_gives_way_to_its_default_for_the_rest() -> None:
    seen: list[dict[str, object]] = []
    client = VoiceClient("http://tts", timeout=5, transport=voice_service(seen, refuse="old"))

    _, voice = await service.speak(client, ["Раз.", "Два.", "Три.", "Четыре.", "Пять."], "old")

    assert [body["voice"] for body in seen] == ["old", None, None]
    assert voice == "qwen3-tts:anchor"


async def test_a_voice_service_that_is_down_is_an_error_for_the_queue() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "busy"})

    client = VoiceClient("http://tts", timeout=5, transport=httpx.MockTransport(down))

    with pytest.raises(httpx.HTTPStatusError):
        await service.speak(client, ["Строка."], None)


@pytest.fixture
def briefing_on(
    api: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[list[dict[str, object]]]:
    """The voice service switched on, faked. Returns the requests it got."""
    from radar.config import get_settings
    from radar.worker import tasks

    monkeypatch.setenv("RADAR_TTS_URL", "http://tts.test")
    monkeypatch.setenv("RADAR_MEDIA_DIR", str(tmp_path))
    get_settings.cache_clear()
    monkeypatch.setattr(tasks.make_briefing, "kiq", AsyncMock())
    seen: list[dict[str, object]] = []
    client = VoiceClient("http://tts.test", timeout=5, transport=voice_service(seen))
    monkeypatch.setattr(service, "get_voice", lambda: client)
    yield seen
    get_settings.cache_clear()


async def management_digest(owner: httpx.AsyncClient, ids: dict[str, int]) -> str:
    """A finished digest written for management."""
    from radar.db import session_scope
    from radar.db.models import Digest

    digest_id = await finished_digest(owner, ids)
    async with session_scope() as session:
        digest = await session.get(Digest, uuid.UUID(digest_id))
        assert digest is not None
        digest.profile_spec = {**digest.profile_spec, "audience": "management"}
        digest.implications = ["Риск: взлом маршрутизаторов - обновить прошивку."]
        digest.highlights = ["Вышел патч для маршрутизаторов."]
    return digest_id


async def test_a_brief_is_voiced_for_the_owner_of_a_management_digest_only(
    api: str,  # noqa: F811
    briefing_on: list[dict[str, object]],
) -> None:
    from radar.worker import tasks

    async with register(api, "irina") as owner, register(api, "oleg") as other:
        ids = await seed_articles()
        specialist = await finished_digest(owner, ids)
        digest_id = await management_digest(owner, ids)

        assert (await owner.get(f"/digests/{specialist}/briefing")).status_code == 409
        assert (await owner.post(f"/digests/{specialist}/briefing")).status_code == 409
        assert (await other.get(f"/digests/{digest_id}/briefing")).status_code == 404
        assert (await other.post(f"/digests/{digest_id}/briefing")).status_code == 404
        state = (await owner.get(f"/digests/{digest_id}/briefing")).json()
        assert state == {"available": True, "voices": [], "briefing": None}

        ordered = await owner.post(f"/digests/{digest_id}/briefing")
        again = await owner.post(f"/digests/{digest_id}/briefing")
        assert ordered.status_code == again.status_code == 202
        assert ordered.json()["status"] == again.json()["status"] == "queued"
        # A second press while it is queued does not queue a second brief.
        kiq = tasks.make_briefing.kiq
        kiq.assert_awaited_once()  # type: ignore[attr-defined]
        briefing_id = uuid.UUID(kiq.await_args.args[0])  # type: ignore[attr-defined]

        assert await service.process(briefing_id)

        briefing = (await owner.get(f"/digests/{digest_id}/briefing")).json()["briefing"]
        assert briefing["status"] == "done"
        assert briefing["voice"] == "qwen3-tts:anchor"
        assert briefing["lines"][0].startswith("Брифинг Tail and Grep для руководства")
        assert briefing["lines"][1].startswith("Что это значит для нас. Риск: взлом")
        # The entries say "CVSS 9.8"; the brief does not.
        assert not any("CVSS" in line for line in briefing["lines"])
        spoken = sum(len(body["sentences"]) for body in briefing_on)  # type: ignore[arg-type]
        assert spoken == len(briefing["lines"])
        listened = await owner.get(briefing["url"].removeprefix("/api/v1"))
        stolen = await other.get(f"/digests/{digest_id}/briefing.wav")
        assert listened.status_code == 200
        assert listened.headers["content-type"] == "audio/wav"
        assert service.duration_ms(listened.content) == briefing["duration_ms"]
        assert stolen.status_code == 404

        assert (await owner.delete(f"/digests/{digest_id}")).status_code == 204
        assert service.audio_path(briefing_id).is_file()
        assert await service.purge_files() == 1
        assert not service.audio_path(briefing_id).exists()


async def test_without_a_voice_service_there_is_no_brief(api: str) -> None:  # noqa: F811
    async with register(api, "anna") as owner:
        digest_id = await management_digest(owner, await seed_articles())

        state = await owner.get(f"/digests/{digest_id}/briefing")
        ordered = await owner.post(f"/digests/{digest_id}/briefing")

    assert state.json() == {"available": False, "voices": [], "briefing": None}
    assert ordered.status_code == 503


async def test_a_brief_left_by_a_dead_worker_can_be_ordered_again(
    api: str,  # noqa: F811
    briefing_on: list[dict[str, object]],
) -> None:
    from sqlalchemy import update

    from radar.db import session_scope
    from radar.db.models import Briefing

    async with register(api, "pavel") as owner:
        digest_id = await management_digest(owner, await seed_articles())
        first = (await owner.post(f"/digests/{digest_id}/briefing")).json()
        async with session_scope() as session:
            await session.execute(
                update(Briefing).values(
                    created_at=datetime.now(UTC) - service.STALE_AFTER - timedelta(minutes=1)
                )
            )

        shown = (await owner.get(f"/digests/{digest_id}/briefing")).json()["briefing"]
        again = await owner.post(f"/digests/{digest_id}/briefing")

    assert first["status"] == "queued"
    assert shown["status"] == "failed"
    assert again.status_code == 202
    assert again.json()["status"] == "queued"
