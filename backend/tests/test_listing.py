# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""Sources without a feed: article links found on a news page or a sitemap,
each article read from its page; and WordPress posts from the REST API."""

import json
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from radar.ingest import listing, pages, wordpress
from radar.ingest.fetch import Ladder
from radar.ingest.pages import MarkupChanged
from tests.test_browser import _Browser, stack_browser  # noqa: F401
from tests.test_fetch import names  # noqa: F401

FIXTURES = Path(__file__).parent / "fixtures" / "listing"
BASE = "https://site.example/news/"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_the_cards_of_a_news_page_are_its_articles() -> None:
    links = listing.find_links(fixture("news.html"), BASE)

    assert [link.url for link in links] == [
        "https://site.example/news/ataka-na-vodokanal-v-sibiri/",
        "https://site.example/news/novaya-uyazvimost-v-plc/",
        # Tracking dropped, the "read more" link to the same page merged.
        "https://site.example/news/2026/09/29/otchet-o-kiberatakah/",
        "https://site.example/news/123456/",
    ]
    assert links[0].title == "Атака на водоканал в Сибири остановила насосные станции"
    assert links[0].published_at == datetime(2026, 10, 1, 6, 30, tzinfo=UTC)
    assert links[1].published_at == datetime(2026, 9, 30, tzinfo=UTC)
    assert links[3].published_at is None


def test_a_selector_takes_the_links_it_names() -> None:
    links = listing.find_links(fixture("news.html"), BASE, selector=".tags")
    assert [link.url for link in links] == [
        "https://site.example/news/tag/scada/",
        "https://site.example/news/tag/ransomware/",
        "https://site.example/news/tag/regulation/",
    ]


def test_hash_routes_of_a_page_drawn_by_script() -> None:
    links = listing.find_links(fixture("spa.html"), "https://bdu.example/#/news")
    # The tag filters of the list are not articles.
    assert [link.url for link in links] == [
        "https://bdu.example/#/news/8313fe39-bee9-4783-a6b0-7d5a47ea184a",
        "https://bdu.example/#/news/c275c550-3bd4-4efd-b2eb-cf50162f5177",
        "https://bdu.example/#/news/5be0a3f5-3a67-48a4-891d-3a65708bf0cb",
    ]


def test_a_page_without_articles_gives_no_links() -> None:
    page = "<html><body><nav><a href='/'>Главная</a><a href='/about/'>О нас</a></nav></body></html>"
    assert listing.find_links(page, BASE) == []


def test_a_sitemap_newest_first() -> None:
    body = fixture("sitemap.xml")
    assert listing.is_sitemap(body)
    links = listing.find_links(body, "https://site.example/sitemap.xml")
    assert [(link.url, link.title) for link in links] == [
        ("https://site.example/news/svezhaya-ataka-na-bank/", "Свежая атака на банк"),
        ("https://site.example/news/vchera-utechka-dannyh-klientov/", ""),
        ("https://site.example/news/starye-novosti-o-zashchite/", ""),
    ]


def test_a_sitemap_index_offers_its_news_sitemap_first() -> None:
    children = listing.sitemap_children(fixture("sitemap-index.xml"), "https://site.example/")
    assert children == [
        "https://site.example/sitemap-news.xml",
        "https://site.example/sitemap-pages.xml",
    ]


@pytest.mark.parametrize(
    ("text", "day"),
    [
        ("Компьютерная атака · 18 мая 2026 г.", datetime(2026, 5, 18, tzinfo=UTC)),
        ("Published May 18, 2026 by the team", datetime(2026, 5, 18, tzinfo=UTC)),
        ("Дата: 18.05.2026", datetime(2026, 5, 18, tzinfo=UTC)),
        ("31 февраля 2026", None),
        ("без даты", None),
    ],
)
def test_dates_in_words(text: str, day: datetime | None) -> None:
    assert pages.date_in_words(text) == day


def test_the_date_a_page_states() -> None:
    assert pages.published_on_page(fixture("article.html")) == datetime(
        2026, 10, 1, 6, 30, tzinfo=UTC
    )
    # The date by the title, not the sidebar's.
    assert pages.published_on_page(
        fixture("article-date-in-words.html"),
        "Geo Likho: новая шпионская угроза для российской авиации",
    ) == datetime(2026, 5, 18, tzinfo=UTC)


def test_an_article_from_its_page() -> None:
    link = listing.Link(url=f"{BASE}ataka-na-vodokanal-v-sibiri/", title="Атака")
    article = pages.article_from_page(link, fixture("article.html"), "ru")

    assert article is not None
    # The listing's title was too short to be one: the page's is taken.
    assert article.title.startswith("Атака на водоканал в Сибири")
    assert article.content is not None
    assert "двухфакторную аутентификацию" in article.content
    assert article.summary == "Злоумышленники получили доступ к SCADA и отключили насосы."
    assert article.published_at == datetime(2026, 10, 1, 6, 30, tzinfo=UTC)
    assert article.image_url == "https://site.example/images/vodokanal.jpg"


def test_a_page_the_browser_did_not_draw_is_left_for_the_next_run() -> None:
    link = listing.Link(url="https://bdu.example/#/news/1", title="Новость о защите АСУ ТП")
    shell = "<html><body><div id=app></div><script src=/app.js></script></body></html>"
    assert pages.article_from_page(link, shell, "ru") is None


def test_wordpress_posts() -> None:
    posts = json.loads(fixture("wp-posts.json"))
    articles = wordpress.parse_posts(posts, "https://cisoclub.ru/wp-json/wp/v2/posts", "ru")

    assert [article.title for article in articles] == [
        "«Гигант»: как выявить утечку данных внутри компании",
        "Фишинг под видом Госуслуг",
    ]
    first, second = articles
    assert first.published_at == datetime(2026, 10, 2, 13, 4, 34, tzinfo=UTC)
    assert first.content is not None
    assert first.content.startswith("Утечка данных внутри компании")
    assert first.image_url == "https://cisoclub.ru/wp-content/uploads/dlp.png"
    assert second.content is None
    assert second.summary == "Новая рассылка."


def test_wordpress_addresses() -> None:
    url = wordpress.posts_url("https://cisoclub.ru/category/news/", category=8)
    assert url == (
        "https://cisoclub.ru/wp-json/wp/v2/posts?per_page=20"
        "&_fields=id%2Clink%2Ctitle%2Cdate_gmt%2Ccontent%2Cexcerpt&categories=8"
    )
    assert wordpress.is_posts_url(url)
    assert wordpress.terms_url("https://cisoclub.ru/x", "categories", "news") == (
        "https://cisoclub.ru/wp-json/wp/v2/categories?slug=news&_fields=id%2Cname"
    )


class _Site(BaseHTTPRequestHandler):
    """A news site: its list, two articles, and the list's ETag."""

    seen: list[str] = []  # noqa: RUF012

    def do_GET(self) -> None:
        self.seen.append(self.path)
        if self.path == "/news/" and self.headers.get("If-None-Match") == '"v1"':
            self.send_response(304)
            self.end_headers()
            return
        if self.path == "/news/":
            body, kind = fixture("news.html"), "text/html"
        elif self.path == "/wp-json/wp/v2/posts":
            body, kind = fixture("wp-posts.json"), "application/json"
        elif self.path.startswith("/news/"):
            body, kind = fixture("article.html"), "text/html"
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("ETag", '"v1"')
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture
def site() -> Iterator[int]:
    _Site.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


async def test_a_news_page_gives_its_new_articles_read_from_their_pages(
    site: int, names: None
) -> None:
    listing_url = f"http://site.test:{site}/news/"
    already = f"http://site.test:{site}/news/novaya-uyazvimost-v-plc/"

    async def known(urls: list[str]) -> set[str]:
        return {url for url in urls if url == already}

    async with httpx.AsyncClient() as client, Ladder(client) as ladder:
        feed = await pages.fetch_listing(
            ladder,
            listing_url,
            language="ru",
            selector=None,
            etag=None,
            last_modified=None,
            known=known,
        )
        again = await pages.fetch_listing(
            ladder,
            listing_url,
            language="ru",
            selector=None,
            etag=feed.etag,
            last_modified=None,
            known=known,
        )

    assert feed.status == "ok"
    assert feed.etag == '"v1"'
    assert [article.url for article in feed.articles] == [
        f"http://site.test:{site}/news/ataka-na-vodokanal-v-sibiri/",
        f"http://site.test:{site}/news/2026/09/29/otchet-o-kiberatakah/",
        f"http://site.test:{site}/news/123456/",
    ]
    # The known article's page was not asked for.
    assert "/news/novaya-uyazvimost-v-plc/" not in _Site.seen
    assert all(article.content for article in feed.articles)
    # The date the listing shows beats the page's.
    assert feed.articles[0].published_at == datetime(2026, 10, 1, 6, 30, tzinfo=UTC)
    assert again.status == "not_modified"


async def test_a_list_drawn_by_script_is_read_by_the_browser(
    site: int, names: None, stack_browser: type[_Browser]
) -> None:
    # The light steps get a page without links; the browser draws the list.
    stack_browser.page = {**stack_browser.page, "html": fixture("news.html")}

    async def known(urls: list[str]) -> set[str]:
        return set(urls)

    async with httpx.AsyncClient() as client, Ladder(client) as ladder:
        feed = await pages.fetch_listing(
            ladder,
            f"http://site.test:{site}/news/ataka/",
            language="ru",
            selector=None,
            etag=None,
            last_modified=None,
            known=known,
        )

    assert feed.status == "ok"
    assert ladder.first is not None
    assert ladder.first.step == "browser"
    assert (
        ladder.first.note == "нет ссылок на статьи на шаге «обычный запрос», прочитан через браузер"
    )


async def test_a_page_with_no_links_on_any_step_is_an_error(site: int, names: None) -> None:
    async def known(urls: list[str]) -> set[str]:
        return set()

    async with httpx.AsyncClient() as client, Ladder(client) as ladder:
        with pytest.raises(MarkupChanged):
            await pages.fetch_listing(
                ladder,
                f"http://site.test:{site}/news/ataka/",
                language="ru",
                selector=None,
                etag=None,
                last_modified=None,
                known=known,
            )


async def test_wordpress_posts_through_the_ladder(site: int, names: None) -> None:
    async with httpx.AsyncClient() as client, Ladder(client) as ladder:
        feed = await wordpress.fetch_posts(
            ladder,
            f"http://site.test:{site}/wp-json/wp/v2/posts",
            language="ru",
            etag=None,
            last_modified=None,
        )
    assert feed.status == "ok"
    assert len(feed.articles) == 2
    assert feed.etag == '"v1"'
