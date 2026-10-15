"""The narration in Yandex SpeechKit: what goes to the cloud and what comes back."""

import base64
import io
import json
import wave

import httpx
import pytest
from pydantic import SecretStr

from radar.config import Settings
from radar.shorts import service
from radar.shorts.voice import narrate
from radar.shorts.yandex_voice import MAX_CHARS, SAMPLE_RATE, YandexVoiceClient, pieces

# Ten milliseconds of sound per character: enough to tell the lines apart.
_BYTES_PER_CHAR = SAMPLE_RATE * 2 // 100


def speechkit(seen: list[httpx.Request], status: int = 200) -> httpx.MockTransport:
    """SpeechKit API v3: the audio of the text in two streamed chunks."""

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "Too long text"}})
        pcm = b"\x01\x00" * (len(json.loads(request.content)["text"]) * _BYTES_PER_CHAR // 2)
        half = len(pcm) // 2
        lines = [
            json.dumps({"result": {"audioChunk": {"data": base64.b64encode(part).decode()}}})
            for part in (pcm[:half], pcm[half:])
        ]
        return httpx.Response(200, text="\n".join(lines) + "\n")

    return httpx.MockTransport(handle)


def client(seen: list[httpx.Request], status: int = 200) -> YandexVoiceClient:
    return YandexVoiceClient(
        SecretStr("key"),
        "b1gfolder",
        timeout=5,
        speaker="filipp",
        transport=speechkit(seen, status),
    )


async def test_each_line_is_spoken_by_the_picked_voice_and_timed_in_one_wav() -> None:
    seen: list[httpx.Request] = []

    narration = await client(seen).speak(["Первая строка.", "Вторая строка, длиннее."], "zahar")

    assert [json.loads(request.content)["text"] for request in seen] == [
        "Первая строка.",
        "Вторая строка, длиннее.",
    ]
    body = json.loads(seen[0].content)
    assert body["hints"] == [{"voice": "zahar"}]
    assert body["outputAudioSpec"]["rawAudio"]["sampleRateHertz"] == SAMPLE_RATE
    assert seen[0].headers["authorization"] == "Api-Key key"
    assert seen[0].headers["x-folder-id"] == "b1gfolder"
    # 14 and 23 characters at ten milliseconds each, the voice service's pause between.
    assert [(s.start_ms, s.end_ms) for s in narration.segments] == [(0, 140), (520, 750)]
    assert narration.voice == "yandex:zahar"
    assert narration.audio is not None
    with wave.open(io.BytesIO(narration.audio), "rb") as reader:
        assert reader.getframerate() == SAMPLE_RATE
        assert reader.getnframes() * 1000 // SAMPLE_RATE == 750


async def test_quotes_and_markup_are_not_sent_to_be_read_out() -> None:
    seen: list[httpx.Request] = []

    await client(seen).speak(["Уязвимость в «FortiMail» (CVE-2025-32756)."])

    assert json.loads(seen[0].content)["text"] == "Уязвимость в FortiMail CVE-2025-32756."


async def test_a_voice_speechkit_does_not_have_gives_way_to_the_default() -> None:
    seen: list[httpx.Request] = []

    narration = await client(seen).speak(["Строка."], "anchor")

    assert json.loads(seen[0].content)["hints"] == [{"voice": "filipp"}]
    assert narration.voice == "yandex:filipp"


def test_a_line_too_long_for_one_request_is_cut_at_sentences_then_at_words() -> None:
    sentence = "Группировка рассылает фишинговые письма промышленным компаниям."
    long_sentence = " ".join(["Слово"] + ["слово"] * 59)

    parts = pieces(" ".join([sentence] * 6) + " " + long_sentence)

    assert all(len(part) <= MAX_CHARS for part in parts)
    # Whole sentences while they fit: three of 63 characters to a part.
    assert parts[0] == " ".join([sentence] * 3)
    assert parts[1] == " ".join([sentence] * 3)
    assert " ".join(parts[2:]) == long_sentence


async def test_a_long_line_is_one_segment_made_of_several_requests() -> None:
    seen: list[httpx.Request] = []
    line = " ".join(["Группировка рассылает фишинговые письма промышленным компаниям."] * 6)

    narration = await client(seen).speak([line])

    assert len(seen) == 2
    assert len(narration.segments) == 1


async def test_speechkit_refusing_leaves_the_video_silent() -> None:
    narration = await narrate(client([], status=400), ["Строка."])

    assert narration.audio is None
    assert narration.voice is None


async def test_the_voices_to_pick_from_mark_the_default() -> None:
    voices = await client([]).voices()

    assert [voice.id for voice in voices if voice.default] == ["filipp"]
    assert {"alena", "zahar", "masha"} <= {voice.id for voice in voices}


def test_speechkit_needs_its_key_and_no_voice_service(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="RADAR_TTS_API_KEY"):
        Settings(tts_provider="yandex", tts_api_key=None)
    settings = Settings(tts_provider="yandex", tts_api_key="key", tts_folder="b1g", tts_url="")
    monkeypatch.setattr(service, "get_settings", lambda: settings)

    assert settings.has_voice
    assert isinstance(service.get_voice(), YandexVoiceClient)
