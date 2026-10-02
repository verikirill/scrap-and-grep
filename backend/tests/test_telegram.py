"""Public Telegram channels: what is taken from a channel's page, and how it is fetched."""

from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import stamina

from radar.images.service import Picture, mirror
from radar.ingest.pages import MarkupChanged
from radar.ingest.telegram import (
    ChannelUnavailable,
    LinkPreview,
    Post,
    articles_of,
    fetch_channel,
    parse_channel,
    parse_channel_page,
    post_picture,
    signatures,
    to_article,
)
from radar.store.articles import NewArticle

PAGE = (Path(__file__).parent / "fixtures" / "telegram" / "channel.html").read_text("utf-8")
NOW = datetime(2026, 10, 2, tzinfo=UTC)
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
TEXT = "Регулятор опубликовал новые требования к защите объектов КИИ на подстанциях."


def articles(page: str = PAGE) -> dict[str, NewArticle]:
    posts = parse_channel_page(page, "radar_ib").posts
    return {article.url: article for article in articles_of(posts, "ru", NOW, signatures(posts))}


def post(*lines: str, number: int = 1, **fields: object) -> Post:
    plain = Post(
        channel="radar_ib",
        id=number,
        published_at=NOW,
        lines=lines,
        links=(),
        hashtags=(),
        picture=None,
        preview=None,
        forwarded_from=None,
        is_ad=False,
    )
    return replace(plain, **fields)  # type: ignore[arg-type]


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Requests go to a mock transport by name, without DNS or retries."""
    from radar.config import get_settings

    monkeypatch.setenv("RADAR_ALLOW_PRIVATE_FEED_HOSTS", "true")
    # curl_cffi does not go through the mock transport: it would ask the
    # real network for the test's hosts.
    monkeypatch.setenv("RADAR_FETCH_IMPERSONATE", "false")
    get_settings.cache_clear()
    with stamina.set_testing(True, attempts=1):
        yield
    get_settings.cache_clear()


def telegram(handle: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


def embed_page(number: int) -> str:
    """The page t.me embeds one post with: the same markup as the channel's page."""
    wrap = '<div class="tgme_widget_message_wrap'
    start = PAGE.index(f'data-post="radar_ib/{number}"')
    return PAGE[PAGE.rindex(wrap, 0, start) : PAGE.index(wrap, start)]


def channel_page(ids: range, *, age: Callable[[int], timedelta] | None = None) -> str:
    """A page of plain posts with the given numbers, a minute apart and ending now."""
    now = datetime.now(UTC)
    posts = "".join(
        f'<div class="tgme_widget_message js-widget_message" data-post="radar_ib/{number}">'
        f'<div class="tgme_widget_message_text js-message_text">Пост {number}. {TEXT}</div>'
        '<a class="tgme_widget_message_date"><time datetime="'
        f"{(now - (age or (lambda n: timedelta(minutes=10_000 - n)))(number)).isoformat()}"
        '"></time></a></div>'
        for number in ids
    )
    return f'<section class="tgme_channel_history">{posts}</section>'


@pytest.mark.parametrize(
    "address",
    [
        "@Radar_IB",
        "radar_ib",
        "t.me/radar_ib",
        "https://t.me/s/radar_ib",
        "https://telegram.me/radar_ib/",
    ],
)
def test_a_channel_is_named_by_any_of_its_addresses(address: str) -> None:
    assert parse_channel(address) == "radar_ib"


@pytest.mark.parametrize(
    "address",
    ["https://example.org/radar_ib", "https://t.me/radar_ib/101", "@ab", "javascript:alert(1)"],
)
def test_other_addresses_are_not_channels(address: str) -> None:
    with pytest.raises(ValueError, match="канал"):
        parse_channel(address)


def test_a_post_with_its_own_text_is_an_article_at_its_telegram_address() -> None:
    found = articles()["https://t.me/radar_ib/101"]

    assert (
        found.title
        == "Новый ботнет Ferrum захватывает открытые API Docker и ставит на хосты майнер"
    )
    assert found.summary.startswith("Об этом сообщили исследователи. Ботнет ищет")
    assert found.content is not None
    assert "#docker" not in found.content
    assert found.tags == ("docker", "ботнеты")
    # Without a photo the picture of the linked page is the story's picture.
    assert found.image_url == "https://cdn4.telesco.pe/file/preview-101.jpg"
    assert found.published_at == datetime(2026, 9, 30, 17, 0, 3, tzinfo=UTC)


def test_a_repost_keeps_its_author_and_loses_emoji_and_the_channel_signature() -> None:
    found = articles()["https://t.me/radar_ib/102"]

    assert found.title == "Энергокомпания перевела резервный ЦОД на отечественную СХД"
    assert found.author == "Другой канал"
    assert found.image_url == "https://cdn4.telesco.pe/file/photo-102.jpg"
    assert found.content is not None
    assert "Подписывайтесь" not in found.content


def test_a_short_post_with_a_link_stands_for_the_page_it_points_to() -> None:
    found = articles()
    # Tracking parameters go; the ampersand t.me escapes twice is read once.
    teaser = found["https://news.example.org/2026/09/30/scada-rce?id=7"]

    assert "https://t.me/radar_ib/103" not in found
    # "Ядерная SCADA." alone is half a headline.
    assert teaser.title == "Ядерная SCADA. Разбираем RCE в контроллере"
    assert (
        teaser.summary
        == "Исследователи нашли способ выполнить код на контроллере без аутентификации."
    )
    # Left for the full-text fetch.
    assert teaser.content is None
    assert teaser.image_url == "https://cdn4.telesco.pe/file/photo-103.jpg"


def test_a_reply_does_not_take_the_text_it_quotes() -> None:
    found = articles()["https://t.me/radar_ib/104"]

    assert found.title.startswith("Регулятор выпустил рекомендации")
    assert found.content is not None
    assert "Ferrum" not in found.content


def test_advertising_greetings_and_service_messages_are_not_news() -> None:
    found = articles()

    assert set(found) == {
        "https://t.me/radar_ib/101",
        "https://t.me/radar_ib/102",
        "https://news.example.org/2026/09/30/scada-rce?id=7",
        "https://t.me/radar_ib/104",
        "https://t.me/radar_ib/108",
    }
    # A line of emoji alone is not a headline.
    assert found["https://t.me/radar_ib/108"].title.startswith("Минэнерго утвердило")


def test_a_headline_keeps_its_units_and_letters_and_loses_links() -> None:
    percent = to_article(post("Курс вырос на 5%", TEXT), "ru", NOW)
    # "й" written as "и" and a combining breve, as some editors save it.
    letters = to_article(
        post("Крайний срок и\u0306 \U0001f525 перенесли 1\ufe0f\u20e3", TEXT), "ru", NOW
    )
    linked = to_article(
        post("Подробности https://example.org/a?x=1 в отчёте вендора", TEXT), "ru", NOW
    )

    assert percent is not None
    assert percent.title == "Курс вырос на 5%"
    assert letters is not None
    assert letters.title == "Крайний срок й перенесли 1"
    assert linked is not None
    assert linked.title == "Подробности в отчёте вендора"


def test_a_teaser_without_a_headline_takes_the_link_card_or_is_dropped() -> None:
    card = LinkPreview(
        url="https://news.example.org/a",
        title="Вендор закрыл уязвимость в контроллерах",
        description="Обновление вышло для трёх линеек.",
        picture=None,
    )
    with_card = to_article(post("Смотрите тут 👇", preview=card), "ru", NOW)
    bare = to_article(
        post("Смотрите тут", "https://news.example.org/b", links=("https://news.example.org/b",)),
        "ru",
        NOW,
    )

    assert with_card is not None
    assert (with_card.url, with_card.title) == ("https://news.example.org/a", card.title)
    assert with_card.summary == "Обновление вышло для трёх линеек."
    assert bare is None


def test_a_video_link_leaves_the_post_an_article_of_its_own() -> None:
    video = "https://www.youtube.com/watch?v=abc"
    found = to_article(post(TEXT, video, links=(video,)), "ru", NOW)

    assert found is not None
    assert found.url == "https://t.me/radar_ib/1"


@pytest.mark.parametrize(
    "marker", ["На правах рекламы", "Рекламодатель: ООО «Ромашка»", "erid 2Vtzqx1ab2", "#реклама"]
)
def test_advertising_is_known_by_any_of_its_markers(marker: str) -> None:
    page = channel_page(range(1, 2)).replace(TEXT, f"{TEXT}<br>{marker}")

    assert parse_channel_page(page, "radar_ib").posts[0].is_ad


def test_a_signature_is_taken_from_the_end_of_posts_only() -> None:
    sign = "Подписывайтесь на «Радар ИБ»"
    posts = [post(sign, f"{TEXT} Номер {n}.", sign, number=n) for n in range(1, 6)]

    cleaned = articles_of(posts, "ru", NOW, signatures(posts))
    few = signatures(posts[:4])

    # The same line opening a post is the post's own.
    assert [article.content for article in cleaned] == [
        f"{sign}\n{TEXT} Номер {n}." for n in range(5, 0, -1)
    ]
    # Four posts are too few to tell a signature from a running header.
    assert few == frozenset()


def test_posts_of_another_channel_or_with_odd_numbers_are_not_taken() -> None:
    page = channel_page(range(1, 4))
    page = page.replace("radar_ib/2", "other_channel/2").replace("radar_ib/3", "radar_ib/³")

    assert [found.id for found in parse_channel_page(page, "radar_ib").posts] == [1]


def test_a_page_whose_posts_cannot_be_read_is_an_error_not_an_empty_channel() -> None:
    no_dates = PAGE.replace("<time datetime=", "<time data-x=")

    with pytest.raises(MarkupChanged):
        parse_channel_page(no_dates, "radar_ib")
    with pytest.raises(MarkupChanged):
        parse_channel_page("<html><body>Something else</body></html>", "radar_ib")
    # A channel without posts yet is fine.
    assert parse_channel_page(channel_page(range(0)), "radar_ib").posts == ()


async def test_a_channel_without_a_preview_is_reported(offline: None) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/s/closed_channel":
            return httpx.Response(302, headers={"location": "https://t.me/closed_channel"})
        return httpx.Response(200, text="<html>Join channel</html>")

    async with telegram(handle) as client:
        with pytest.raises(ChannelUnavailable):
            await fetch_channel(
                client, "https://t.me/s/closed_channel", language="ru", last_post_id=None
            )


async def test_posts_are_read_back_to_the_last_one_seen_and_no_further(offline: None) -> None:
    asked: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        before = request.url.params.get("before")
        ids = range(101, 121) if before is None else range(81, int(before))
        return httpx.Response(200, text=channel_page(ids))

    async with telegram(handle) as client:
        result = await fetch_channel(
            client, "https://t.me/s/radar_ib", language="ru", last_post_id=97
        )
        nothing_new = await fetch_channel(
            client, "https://t.me/s/radar_ib", language="ru", last_post_id=120
        )

    assert asked == [
        "https://t.me/s/radar_ib",
        "https://t.me/s/radar_ib?before=101",
        "https://t.me/s/radar_ib",
    ]
    numbers = sorted(int(article.url.rsplit("/", 1)[1]) for article in result.articles)
    assert numbers == list(range(98, 121))
    assert result.last_post_id == 120
    assert nothing_new.status == "not_modified"
    assert nothing_new.last_post_id == 120


async def test_a_new_channel_is_read_three_days_back_or_its_last_page_if_quiet(
    offline: None,
) -> None:
    def busy(request: httpx.Request) -> httpx.Response:
        before = int(request.url.params.get("before", 61))
        # A post every two hours: three days are 36 posts.
        return httpx.Response(
            200,
            text=channel_page(
                range(max(1, before - 20), before), age=lambda n: timedelta(hours=2 * (61 - n) + 1)
            ),
        )

    def quiet(request: httpx.Request) -> httpx.Response:
        before = request.url.params.get("before")
        ids = range(1, 6) if before is None else range(0)
        return httpx.Response(200, text=channel_page(ids, age=lambda n: timedelta(days=30 - n)))

    async with telegram(busy) as client:
        recent = await fetch_channel(
            client, "https://t.me/s/radar_ib", language="ru", last_post_id=None
        )
    async with telegram(quiet) as client:
        last_page = await fetch_channel(
            client, "https://t.me/s/radar_ib", language="ru", last_post_id=None
        )

    # Posts 26 to 60 are younger than three days.
    assert len(recent.articles) == 35
    assert recent.last_post_id == 60
    assert len(last_page.articles) == 5


async def test_telegram_me_answers_when_t_me_does_not(offline: None) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "t.me":
            raise httpx.ConnectError("blocked", request=request)
        before = request.url.params.get("before")
        return httpx.Response(200, text=channel_page(range(1, 4) if before is None else range(0)))

    async with telegram(handle) as client:
        result = await fetch_channel(
            client, "https://t.me/s/radar_ib", language="ru", last_post_id=None
        )

    # The article keeps the canonical t.me address whichever host answered.
    assert {article.url for article in result.articles} == {
        f"https://t.me/radar_ib/{number}" for number in range(1, 4)
    }


async def test_a_refusal_from_t_me_is_not_asked_again_elsewhere(offline: None) -> None:
    hosts: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        return httpx.Response(404)

    async with telegram(handle) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_channel(client, "https://t.me/s/radar_ib", language="ru", last_post_id=None)

    assert hosts == ["t.me"]


async def test_a_post_picture_comes_from_the_post_not_from_the_channel_avatar(
    offline: None,
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("embed") == "1"
        return httpx.Response(200, text=embed_page(int(request.url.path.rsplit("/", 1)[1])))

    async with telegram(handle) as client:
        photo = await post_picture(client, "https://t.me/radar_ib/102")
        text_only = await post_picture(client, "https://t.me/radar_ib/104")

    assert photo == "https://cdn4.telesco.pe/file/photo-102.jpg"
    assert text_only is None


async def test_an_expired_picture_address_is_looked_up_again(offline: None) -> None:
    from radar.db.models import Article

    class Memory:
        def __init__(self) -> None:
            self.saved: dict[str, bytes] = {}

        async def put(self, key: str, data: bytes) -> None:
            self.saved[key] = data

        async def get(self, key: str) -> bytes | None:
            return self.saved.get(key)

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(("/stale.jpg", "/photo-104.jpg")):
            return httpx.Response(404)
        if request.url.path.endswith("/photo-102.jpg"):
            return httpx.Response(200, content=JPEG)
        return httpx.Response(200, text=embed_page(int(request.url.path.rsplit("/", 1)[1])))

    stale = Article(
        url="https://t.me/radar_ib/102", image_url="https://cdn4.telesco.pe/file/stale.jpg"
    )
    # The page gives no other address: there is nothing to try again.
    gone = Article(
        url="https://t.me/radar_ib/104", image_url="https://cdn4.telesco.pe/file/photo-104.jpg"
    )
    store = Memory()
    async with telegram(handle) as client:
        picture = await mirror(stale, client, store)
        nothing = await mirror(gone, client, store)

    assert picture == Picture(JPEG, "jpg")
    assert stale.image_url == "https://cdn4.telesco.pe/file/photo-102.jpg"
    assert stale.image_key in store.saved
    assert nothing is None
    assert gone.image_key is None
