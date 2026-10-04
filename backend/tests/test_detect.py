# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""Any address a reader pastes: what it is, how it is read and what it has,
found before anything is saved."""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from radar.ingest import detect, telegram
from radar.ingest.detect import NotFound
from tests.test_fetch import names  # noqa: F401
from tests.test_listing import fixture
from tests.test_telegram import channel_page, offline  # noqa: F401

FEED = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Блог об ИБ</title><link>https://site.test/blog/</link>
<item><title>Первая заметка о защите АСУ ТП</title><link>https://site.test/blog/1</link>
<pubDate>Wed, 01 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Вторая заметка об атаках на подстанции</title><link>https://site.test/blog/2</link>
<pubDate>Thu, 02 Oct 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""
BLOG = (
    '<html><head><title>Блог</title><link rel="alternate" type="application/rss+xml" '
    'href="/blog/ib.xml"></head><body><p>Блог</p></body></html>'
)
WORDPRESS = (
    "<html><head><title>CISO Club</title>"
    '<link rel="stylesheet" href="/wp-content/themes/x/style.css"></head><body></body></html>'
)
NOTHING = "<html><head><title>Пусто</title></head><body><a href='/about/'>О нас</a></body></html>"


class _Site(BaseHTTPRequestHandler):
    """A blog with a feed away from the usual paths, a news page without one, a WordPress site whose
    feed is closed, and a page with no articles at all."""

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        routes = {
            "/blog/ib.xml": (200, FEED, "application/rss+xml"),
            "/blog/": (200, BLOG, "text/html"),
            "/news/": (200, fixture("news.html"), "text/html"),
            "/wp/": (200, WORDPRESS, "text/html"),
            "/wp/feed/": (403, "Forbidden", "text/html"),
            "/wp-json/wp/v2/posts": (200, fixture("wp-posts.json"), "application/json"),
            "/empty/": (200, NOTHING, "text/html"),
        }
        status, body, kind = routes.get(path, (404, "Not found", "text/html"))
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture
def site(names: None) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://site.test:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


async def found(address: str, selector: str | None = None) -> detect.Found:
    async with httpx.AsyncClient() as client:
        return await detect.detect(address, client, selector)


async def test_a_feed_is_a_feed(site: str) -> None:
    feed = await found(f"{site}/blog/ib.xml")

    assert feed.kind == "rss"
    assert feed.address == f"{site}/blog/ib.xml"
    assert feed.name == "Блог об ИБ"
    assert feed.language == "ru"
    # Newest first.
    assert [sample.url for sample in feed.samples] == [
        "https://site.test/blog/2",
        "https://site.test/blog/1",
    ]
    assert feed.fetch_method == "plain"


async def test_a_page_is_read_through_the_feed_it_names(site: str) -> None:
    feed = await found(f"{site}/blog/")

    assert feed.kind == "rss"
    assert feed.address == f"{site}/blog/ib.xml"
    assert len(feed.samples) == 2


async def test_a_news_page_without_a_feed_is_read_from_its_links(site: str) -> None:
    page = await found(f"{site}/news/")

    assert page.kind == "page"
    assert page.address == f"{site}/news/"
    # The page's own title, as it has no feed to name it.
    assert page.name == "Новости - Пример"
    assert [sample.url for sample in page.samples] == [
        f"{site}/news/ataka-na-vodokanal-v-sibiri/",
        f"{site}/news/novaya-uyazvimost-v-plc/",
        f"{site}/news/2026/09/29/otchet-o-kiberatakah/",
    ]
    assert page.link_selector is None


async def test_a_selector_names_the_links_of_a_page(site: str) -> None:
    page = await found(f"{site}/news/", selector=".tags")

    assert page.kind == "page"
    assert page.link_selector == ".tags"
    assert page.samples[0].url == f"{site}/news/tag/scada/"


async def test_a_wordpress_site_with_a_closed_feed_is_read_through_its_api(site: str) -> None:
    posts = await found(f"{site}/wp/")

    assert posts.kind == "wordpress"
    assert posts.address.startswith(f"{site}/wp-json/wp/v2/posts?")
    assert posts.samples[0].title == "«Гигант»: как выявить утечку данных внутри компании"


async def test_a_page_with_no_articles_asks_for_a_selector(site: str) -> None:
    with pytest.raises(NotFound, match="CSS-селектор"):
        await found(f"{site}/empty/")


@pytest.mark.parametrize(
    ("address", "said"),
    [
        ("http://intranet.test/news/", "внутреннюю сеть"),
        ("ftp://site.test/news/", "похоже на корректный адрес"),
    ],
)
async def test_an_address_that_cannot_be_read(site: str, address: str, said: str) -> None:
    with pytest.raises(NotFound, match=said):
        await found(address)


async def test_a_channel_by_its_name(offline: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def title(_: httpx.AsyncClient, name: str) -> str:
        return "Радар ИБ"

    monkeypatch.setattr(telegram, "channel_title", title)

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=channel_page(range(1, 6)), request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        channel = await detect.detect("@Radar_IB", client)

    assert channel.kind == "telegram"
    assert channel.address == "radar_ib"
    assert channel.name == "Радар ИБ"
    assert [sample.url for sample in channel.samples] == [
        "https://t.me/radar_ib/5",
        "https://t.me/radar_ib/4",
        "https://t.me/radar_ib/3",
    ]


async def test_a_host_with_no_address_is_no_site(
    site: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from radar.ingest import browser, fetch, net, solver
    from radar.ingest.net import UnresolvableHostError

    async def resolve(url: str) -> str | None:
        raise UnresolvableHostError(f"cannot resolve host {httpx.URL(url).host}")

    for module in (net, fetch, solver, browser):
        monkeypatch.setattr(module, "resolve_public", resolve)

    with pytest.raises(NotFound, match="Сайт не найден"):
        await found("https://gone.test/news/")
