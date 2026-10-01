"""Publishing to Telegram, without a database: schedule, markup, the calls a
post turns into, what the writer may say, and how Telegram's errors read."""

import json
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from radar.publishing.content import Button, Media, PostContent, requests_for
from radar.publishing.markup import CAPTION_LIMIT, canonical, plain_text, to_classic
from radar.publishing.schedule import digest_slot, slots_on, slots_to_prepare
from radar.publishing.settings import ChannelSettings, DigestPost, Links, Schedule, Style
from radar.publishing.telegram import TelegramClient, TelegramError, message_link
from radar.publishing.writer import (
    NewsDraft,
    OllamaPostWriter,
    Story,
    Voice,
    _NewsOut,
    check_news,
    render_news,
)

MOSCOW = ZoneInfo("Europe/Moscow")
TOKEN = "123456789:AAH" + "x" * 32


def story(**extra: object) -> Story:
    fields: dict[str, object] = {
        "article_id": 7,
        "title": "Siemens закрыла уязвимость в SIMATIC S7-1500",
        "summary": "Компания выпустила обновление 3.1. Уязвимость оценена в 9.8 балла CVSS.",
        "body": "Атакующий мог удалённо остановить ПЛК. Затронуты 12 моделей.",
        "url": "https://example.org/siemens",
        "source": "SecurityWeek",
        "published_at": datetime(2026, 9, 30, 9, tzinfo=UTC),
    }
    return Story(**(fields | extra))  # type: ignore[arg-type]


def voice(**extra: object) -> Voice:
    fields: dict[str, object] = {
        "channel": "Бэкдор",
        "username": "backdoor",
        "audience": "инженеры АСУ ТП",
        "style": Style(signature="Бэкдор"),
        "links": Links(),
    }
    return Voice(**(fields | extra))  # type: ignore[arg-type]


# Schedule


def test_an_interval_schedule_posts_inside_the_window_on_chosen_days() -> None:
    schedule = Schedule(every_minutes=120, window_start="09:00", window_end="15:00", days=(0,))

    monday = slots_on(date(2026, 9, 28), schedule, "channel")
    tuesday = slots_on(date(2026, 9, 29), schedule, "channel")

    assert [slot.astimezone(MOSCOW).strftime("%H:%M") for slot in monday] == [
        "09:00",
        "11:00",
        "13:00",
        "15:00",
    ]
    assert tuesday == []


def test_jitter_moves_a_slot_the_same_way_every_time_and_keeps_the_cap() -> None:
    schedule = Schedule(mode="times", times=("10:00", "18:30"), jitter_minutes=15, max_per_day=1)

    first = slots_on(date(2026, 9, 30), schedule, "channel-a")
    again = slots_on(date(2026, 9, 30), schedule, "channel-a")

    assert first == again
    assert len(first) == 1
    shift = first[0].astimezone(MOSCOW) - datetime(2026, 9, 30, 10, tzinfo=MOSCOW)
    assert abs(shift) <= timedelta(minutes=15)


def test_a_slot_is_prepared_ahead_of_time_and_a_long_missed_one_is_skipped() -> None:
    schedule = Schedule(mode="times", times=("10:00", "12:00"), prepare_minutes=30)
    slot = datetime(2026, 9, 30, 12, tzinfo=MOSCOW)

    assert slots_to_prepare(slot - timedelta(minutes=20), schedule, "c") == [slot]
    assert slots_to_prepare(slot - timedelta(minutes=45), schedule, "c") == []
    # The stack was down for an hour: the 10:00 slot is not posted at 11:10.
    assert slots_to_prepare(datetime(2026, 9, 30, 11, 10, tzinfo=MOSCOW), schedule, "c") == []


def test_the_weekly_round_up_has_one_slot_a_week() -> None:
    schedule = Schedule(prepare_minutes=30)
    digest = DigestPost(enabled=True, weekday=4, time="18:00")
    friday = datetime(2026, 10, 2, 18, tzinfo=MOSCOW)

    assert digest_slot(friday - timedelta(minutes=10), digest, schedule) == friday
    assert digest_slot(friday - timedelta(days=1), digest, schedule) is None


def test_settings_refuse_a_window_that_ends_before_it_starts_and_odd_utm() -> None:
    with pytest.raises(ValueError, match="window"):
        Schedule(window_start="20:00", window_end="09:00")
    with pytest.raises(ValueError, match="utm"):
        Links(utm="utm_source=<script>")
    assert ChannelSettings.model_validate({}).links.mode == "inline"


# Markup


def test_markup_keeps_the_allowlist_and_drops_the_rest() -> None:
    html = canonical(
        "<p>⚡ <strong>Claude</strong> <script>alert(1)</script>умеет "
        '<a href="javascript:steal()">моды</a> и <a href="https://ex.org/?a=1&b=2">тут</a></p>'
        '<div onclick="x()">Дальше <em>текст</em><span class="tg-spoiler">тайна</span></div>'
    )

    for unsafe in ("script", "alert", "javascript", "onclick"):
        assert unsafe not in html
    assert '<a href="https://ex.org/?a=1&amp;b=2">тут</a>' in html
    assert "<i>текст</i>" in html
    assert "<tg-spoiler>тайна</tg-spoiler>" in html


def test_a_classic_post_turns_blocks_into_lines_and_bullets() -> None:
    html = (
        "<h2>Итог</h2><p>Первый абзац.</p><ul><li>Один</li><li>Два</li></ul>"
        "<blockquote><p>Цитата</p></blockquote>"
    )

    assert to_classic(html) == (
        "<b>Итог</b>\n\nПервый абзац.\n\n• Один\n• Два\n\n<blockquote>Цитата</blockquote>"
    )
    assert plain_text(html).splitlines()[0] == "Итог"


# The calls a post turns into


def test_a_short_post_with_a_picture_is_a_photo_with_a_caption_and_a_button() -> None:
    content = PostContent(
        html="<p><b>Новость</b> коротко.</p>",
        media=(Media(url="https://cdn.example.org/a.jpg"),),
        buttons=(Button(text="Читать", url="https://example.org/a"),),
        silent=True,
    )

    [(method, payload)] = requests_for(content, -1001)

    assert method == "sendPhoto"
    assert payload["photo"] == "https://cdn.example.org/a.jpg"
    assert payload["caption"] == "<b>Новость</b> коротко."
    assert payload["parse_mode"] == "HTML"
    assert payload["disable_notification"] is True
    assert payload["reply_markup"]["inline_keyboard"][0][0]["url"] == "https://example.org/a"


def test_a_caption_too_long_for_the_picture_becomes_text_with_a_large_preview() -> None:
    content = PostContent(
        html=f"<p>{'слово ' * (CAPTION_LIMIT // 5)}</p>",
        media=(Media(url="https://cdn.example.org/a.jpg"),),
    )

    [(method, payload)] = requests_for(content, -1001)

    assert method == "sendMessage"
    assert payload["link_preview_options"] == {
        "url": "https://cdn.example.org/a.jpg",
        "prefer_large_media": True,
        "show_above_text": True,
    }


def test_a_rich_post_goes_through_send_rich_message_with_media_and_buttons() -> None:
    content = PostContent(
        format="rich",
        html="<h2>Главное</h2><ul><li>Раз</li></ul>",
        media=(
            Media(url="https://cdn.example.org/a.jpg"),
            Media(url="https://cdn.example.org/b.jpg"),
        ),
        buttons=(Button(text="Источник", url="https://example.org/a"),),
    )

    [(method, payload)] = requests_for(content, -1001)

    html = payload["rich_message"]["html"]
    assert method == "sendRichMessage"
    assert html.startswith("<tg-slideshow><img src=")
    assert "<h2>Главное</h2><ul><li>Раз</li></ul>" in html
    assert '<tg-button type="url" url="https://example.org/a">Источник</tg-button>' in html


def test_a_post_names_what_telegram_would_refuse() -> None:
    album = PostContent(
        html="<p>Текст</p>",
        media=(Media(url="https://a.org/1.jpg"), Media(url="https://a.org/2.jpg")),
        buttons=(Button(text="Ссылка", url="https://a.org"),),
    )

    assert album.problems() == ["К альбому Telegram не прикрепляет кнопки."]
    with pytest.raises(ValueError, match="http"):
        Media(url="javascript:alert(1)")


# What the writer may say


def test_the_writer_drops_lines_with_invented_figures_or_links() -> None:
    out = _NewsOut(
        headline="Siemens закрыла дыру в 40 моделях",
        lead="Звоните 8 800 555-35-35",
        paragraphs=["Обновление 3.1 вышло. Оценка 9.8 по CVSS.", "Подробнее на evil.example.com"],
        bullets=["Затронуты 12 моделей", "Затронуты 13 моделей"],
        ending="Наконец-то!",
        emphasis=["Обновление 3.1 вышло", "чего нет в тексте"],
        cta="Подробности",
    )

    draft = check_news(out, story(), voice())

    # 40 is not in the article: the article's own title stands in.
    assert draft.headline == story().title
    assert draft.lead == ""
    assert draft.paragraphs == ("Обновление 3.1 вышло. Оценка 9.8 по CVSS.",)
    assert draft.bullets == ("Затронуты 12 моделей",)
    assert draft.emphasis == ("Обновление 3.1 вышло",)


def test_the_writer_drops_addresses_and_handles_the_article_does_not_mention() -> None:
    out = _NewsOut(
        headline="Siemens закрыла уязвимость в SIMATIC S7-1500",
        paragraphs=[
            "Подробности в канале t.me/scam_news.",
            "Пишите в поддержку @scam_support.",
            "Скачайте патч на bit.ly/patch-now.",
            "Патч раздаёт siemens-update.xyz/s7.",
            "Обновление 3.1 работает и с Node.js.",
        ],
        ending="Наконец-то!",
    )

    draft = check_news(out, story(summary="Обновление 3.1 работает с Node.js."), voice())

    # Telegram turns a bare domain or @name into a link in the channel's voice;
    # a name with a dot stays only when the article itself has it.
    assert draft.paragraphs == ("Обновление 3.1 работает и с Node.js.",)


def test_markdown_from_the_model_becomes_emphasis_and_the_lead_loses_its_own_dash() -> None:
    out = _NewsOut(
        headline="**Siemens закрыла уязвимость в SIMATIC S7-1500**",
        lead="— атакующий мог удалённо остановить ПЛК",
        paragraphs=["Компания выпустила **обновление 3.1**, затронуты 12 моделей."],
    )

    draft = check_news(out, story(), voice())
    html = render_news(draft, voice(), None)

    assert draft.headline == "Siemens закрыла уязвимость в SIMATIC S7-1500"
    assert draft.lead == "атакующий мог удалённо остановить ПЛК"
    assert draft.paragraphs == ("Компания выпустила обновление 3.1, затронуты 12 моделей.",)
    assert "S7-1500</b> — атакующий" in html
    assert "выпустила <b>обновление 3.1</b>, затронуты" in html
    assert "*" not in html


def test_a_news_post_reads_like_the_channel() -> None:
    draft = NewsDraft(
        headline="Siemens закрыла уязвимость",
        lead="атакующий мог остановить ПЛК",
        paragraphs=("Обновление уже вышло.",),
        bullets=("S7-1500", "S7-1200"),
        ending="Наконец-то!",
        emphasis=("уже вышло",),
    )

    html = render_news(draft, voice(), "https://example.org/siemens?utm_source=tg")

    assert html.startswith("<p>⚡ <b>Siemens закрыла уязвимость</b> — атакующий")
    assert "<p>Обновление <b>уже вышло</b>.</p>" in html
    assert "<ul><li>S7-1500</li><li>S7-1200</li></ul>" in html
    assert '<a href="https://example.org/siemens?utm_source=tg">здесь</a>' in html
    assert html.endswith('<p><a href="https://t.me/backdoor">Бэкдор</a></p>')
    # No link at all when the channel does not want one.
    assert 'href="https://example.org' not in render_news(
        draft, voice(links=Links(mode="none")), None
    )


class RecordingChat:
    name = "fake"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def ask(self, schema: type, system: str, user: str) -> _NewsOut:
        self.prompts.append(system + "\n" + user)
        return _NewsOut(headline="Siemens закрыла уязвимость", paragraphs=["Обновление вышло."])


async def test_the_model_is_told_how_other_channels_told_the_story() -> None:
    chat = RecordingChat()
    writer = OllamaPostWriter(chat)  # type: ignore[arg-type]

    await writer.news(story(), voice(others=("Siemens срочно латает S7-1500.",)))

    assert "Siemens срочно латает S7-1500." in chat.prompts[0]
    assert "Напиши заметно иначе" in chat.prompts[0]


# Telegram's answers


def answering(
    status: int, body: dict[str, object], seen: list[httpx.Request]
) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handle)


async def test_a_rate_limit_and_a_lost_channel_are_told_apart() -> None:
    seen: list[httpx.Request] = []
    limited = TelegramClient(
        TOKEN,
        base_url="https://bot.test",
        transport=answering(
            429,
            {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 7},
            },
            seen,
        ),
    )
    kicked = TelegramClient(
        TOKEN,
        base_url="https://bot.test",
        transport=answering(
            403, {"ok": False, "error_code": 403, "description": "Forbidden: bot was kicked"}, seen
        ),
    )

    with pytest.raises(TelegramError) as rate:
        await limited.send("sendMessage", {"chat_id": 1, "text": "x"})
    with pytest.raises(TelegramError) as gone:
        await kicked.send("sendMessage", {"chat_id": 1, "text": "x"})

    assert rate.value.is_rate_limited
    assert rate.value.retry_after == 7
    assert gone.value.lost_access
    assert not gone.value.is_rate_limited
    # The token is in the URL Telegram needs, and nowhere in what is raised.
    assert TOKEN not in str(rate.value)
    assert TOKEN not in str(gone.value)


async def test_an_uploaded_picture_goes_as_multipart_with_json_fields() -> None:
    seen: list[httpx.Request] = []
    client = TelegramClient(
        TOKEN,
        base_url="https://bot.test",
        transport=answering(200, {"ok": True, "result": {"message_id": 5}}, seen),
    )

    result = await client.send_file(
        "sendPhoto",
        {"chat_id": -1001, "caption": "<b>x</b>", "reply_markup": {"inline_keyboard": []}},
        field="photo",
        filename="picture.jpg",
        data=b"\xff\xd8\xffdata",
        content_type="image/jpeg",
    )

    body = seen[0].content
    assert result == {"message_id": 5}
    assert b'name="photo"; filename="picture.jpg"' in body
    assert json.dumps({"inline_keyboard": []}).encode() in body


def test_a_post_link_is_public_by_name_and_private_by_id() -> None:
    assert message_link("backdoor", -1001234, 15) == "https://t.me/backdoor/15"
    assert message_link(None, -1001234567890, 15) == "https://t.me/c/1234567890/15"
