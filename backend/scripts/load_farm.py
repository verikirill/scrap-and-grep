"""Sites for the ingest load test (scripts/load_ingest.py): many sources, one process.

Each source is a host of its own, `s001.farm` and on, so that politeness
(one request per second to a host) paces them as it paces real sites:

- `feed`: an RSS feed of the last 30 items, half with the full text in it
  and half a teaser, whose source then reads every new article page;
- `page`: a news section in plain HTML, its links found by their repeated
  markup, with no feed (ingest/listing.py);
- `js`: a news section and articles drawn by script after a pause, an empty
  page without it, so the ladder climbs to the stack's browser.

Sources publish on a clock of the farm's own: `POST /tick?minutes=15` moves
it on by a polling interval, so a day of publishing takes no day to test.
How often each source publishes follows the snapshot of October 3: per
source per day, the twenty quantiles below, 3.4 on average. Half the sources
answer a repeated request with 304, as about half of the real ones do.

Every answer waits 50-400 ms, as a remote site would. `GET /stats` counts the
requests by kind of page and by who asked: the stack's browser (Firefox),
the impersonating steps (Chrome) or the plain bot.

    uvicorn load_farm:app --host 0.0.0.0 --port 8099
"""

import asyncio
import hashlib
import json
import os
import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

# Publications per source per day, by quantile (data/samples, the last week).
RATES = (0.05, 0.05, 0.14, 0.14, 0.14, 0.14, 0.29, 0.57, 0.86, 1.14,
         1.43, 1.71, 2.43, 2.71, 2.86, 4.0, 4.86, 5.71, 11.0, 27.29)  # fmt: skip
FEED_ITEMS = 30
PAGE_ITEMS = 20
# How long a script-drawn page takes to draw itself, in seconds: with the
# browser's own waits a render takes 6-9 s, as real ones did when the
# browser was measured (БДУ АСУ ТП 6,3-7,7 s, Forbes 6,0, Broadcom 8,6).
DRAW_DELAY = tuple(float(part) for part in os.environ.get("FARM_DRAW", "3,6").split(","))

FEEDS = int(os.environ.get("FARM_FEEDS", "140"))
PAGES = int(os.environ.get("FARM_PAGES", "30"))
SCRIPTED = int(os.environ.get("FARM_JS", "30"))
DOMAIN = os.environ.get("FARM_DOMAIN", "farm")

WORDS = (
    "уязвимость",
    "атака",
    "группировка",
    "эксплойт",
    "обновление",
    "патч",
    "сервер",
    "протокол",
    "контроллер",
    "подстанция",
    "шифровальщик",
    "фишинг",
    "учётная",
    "запись",
    "доступ",
    "сеть",
    "сегмент",
    "журнал",
    "событие",
    "инцидент",
    "расследование",
    "исследователи",
    "компания",
    "продукт",
    "версия",
    "злоумышленники",
    "вредоносный",
    "загрузчик",
    "бэкдор",
    "домен",
)


def kind_of(index: int) -> str:
    if index < FEEDS:
        return "feed"
    return "page" if index < FEEDS + PAGES else "js"


def host_of(index: int) -> str:
    return f"s{index + 1:03d}.{DOMAIN}"


class Clock:
    """The farm's time: real time at start, moved on by /tick."""

    def __init__(self) -> None:
        self.start = datetime.now(UTC)
        self.shift = timedelta()

    def now(self) -> datetime:
        return datetime.now(UTC) + self.shift


CLOCK = Clock()
STATS: Counter[str] = Counter()


def schedule(index: int) -> tuple[float, float]:
    """(interval in seconds, phase) of a source's publications."""
    rate = RATES[index % len(RATES)]
    interval = 86_400 / rate
    phase = random.Random(index).random() * interval  # noqa: S311
    return interval, phase


def origin(index: int) -> tuple[datetime, float]:
    """When a source's item 0 came out, and the interval between items.

    A feed's worth of intervals before the farm started, so even the
    quietest source has something to show on its first poll."""
    interval, phase = schedule(index)
    return CLOCK.start - timedelta(seconds=interval * (FEED_ITEMS - phase / interval)), interval


def published(index: int, limit: int) -> list[tuple[int, datetime]]:
    """The source's latest `limit` items, newest first: (number, time)."""
    first_out, interval = origin(index)
    elapsed = (CLOCK.now() - first_out).total_seconds()
    if elapsed < 0:
        return []
    last = int(elapsed // interval)
    first = max(0, last - limit + 1)
    return [
        (number, first_out + timedelta(seconds=number * interval))
        for number in range(last, first - 1, -1)
    ]


def item(index: int, number: int) -> datetime | None:
    """When item `number` came out, or None if it has not yet."""
    first_out, interval = origin(index)
    moment = first_out + timedelta(seconds=number * interval)
    return moment if number >= 0 and moment <= CLOCK.now() else None


def text(index: int, number: int, words: int = 520) -> str:
    rng = random.Random(index * 100_003 + number)  # noqa: S311
    sentences = []
    while sum(len(s.split()) for s in sentences) < words:
        length = rng.randint(8, 18)
        sentence = " ".join(rng.choice(WORDS) for _ in range(length))
        sentences.append(sentence.capitalize() + ".")
    paragraphs = [" ".join(sentences[i : i + 5]) for i in range(0, len(sentences), 5)]
    return "\n".join(f"<p>{p}</p>" for p in paragraphs)


def title(index: int, number: int) -> str:
    rng = random.Random(index * 7_919 + number)  # noqa: S311
    return " ".join(rng.choice(WORDS) for _ in range(6)).capitalize() + f" ({index}-{number})"


def path_of(number: int) -> str:
    """An article's address with a slug, as real sites have: `/news/12` alone
    reads as a menu item to ingest/listing.py."""
    return f"/news/{number}-novost-ob-ugroze"


def source_index(request: Request) -> int:
    host = (request.headers.get("host") or "").split(":")[0]
    label = host.split(".", 1)[0]
    if not label.startswith("s") or not label[1:].isdigit():
        raise LookupError(host)
    index = int(label[1:]) - 1
    if not 0 <= index < FEEDS + PAGES + SCRIPTED:
        raise LookupError(host)
    return index


def who(request: Request) -> str:
    agent = request.headers.get("user-agent", "")
    if "Firefox" in agent:
        return "browser"
    if "Chrome" in agent:
        return "chrome"
    return "bot"


async def answer(request: Request, page: str) -> int | None:
    """The common part of every answer: the wait, the count, the source."""
    await asyncio.sleep(random.uniform(0.05, 0.4))  # noqa: S311
    STATS[f"{page}:{who(request)}"] += 1
    try:
        return source_index(request)
    except LookupError:
        return None


def not_modified(request: Request, index: int, tag: str) -> Response | None:
    if index % 2 == 0 and request.headers.get("if-none-match") == tag:
        STATS["304"] += 1
        return Response(status_code=304, headers={"ETag": tag})
    return None


def etag(items: list[tuple[int, datetime]]) -> str:
    return '"' + hashlib.sha1(repr(items[:1]).encode(), usedforsecurity=False).hexdigest() + '"'


async def feed(request: Request) -> Response:
    index = await answer(request, "feed")
    if index is None or kind_of(index) != "feed":
        return PlainTextResponse("no such feed", status_code=404)
    items = published(index, FEED_ITEMS)
    tag = etag(items)
    if (unchanged := not_modified(request, index, tag)) is not None:
        return unchanged
    base = f"http://{host_of(index)}"
    full = index % 2 == 0
    entries = []
    for number, moment in items:
        body = text(index, number) if full else text(index, number, words=40)
        entries.append(
            f"<item><title>{title(index, number)}</title>"
            f"<link>{base}{path_of(number)}</link><guid>{base}{path_of(number)}</guid>"
            f"<pubDate>{format_datetime(moment)}</pubDate>"
            f"<description><![CDATA[{body}]]></description></item>"
        )
    xml = (
        '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
        f"<title>Farm {index}</title><link>{base}/</link><description>load</description>"
        + "".join(entries)
        + "</channel></rss>"
    )
    headers = {"ETag": tag} if index % 2 == 0 else {}
    return Response(xml, media_type="application/rss+xml; charset=utf-8", headers=headers)


def listing_html(index: int, items: list[tuple[int, datetime]]) -> str:
    cards = "".join(
        f'<article class="news-card"><a href="{path_of(number)}">{title(index, number)}</a>'
        f'<time datetime="{moment.isoformat()}">{moment:%d.%m.%Y}</time>'
        f"<p>{title(index, number + 1)}</p></article>"
        for number, moment in items
    )
    nav = "".join(f'<a href="/{part}">{part}</a>' for part in ("about", "contacts", "tags"))
    return f"<nav>{nav}</nav><main><h1>Новости</h1>{cards}</main><footer>Farm {index}</footer>"


def article_html(index: int, number: int, moment: datetime) -> str:
    return (
        f"<article><h1>{title(index, number)}</h1>"
        f'<time datetime="{moment.isoformat()}">{moment:%d.%m.%Y}</time>'
        f"{text(index, number)}</article>"
    )


def page_shell(head: str, body: str) -> str:
    return (
        f'<!doctype html><html lang="ru"><head><meta charset="utf-8">{head}</head>'
        f"<body>{body}</body></html>"
    )


def scripted(path: str) -> HTMLResponse:
    """An empty application that draws `path` from the farm's API."""
    return HTMLResponse(
        page_shell(
            "<title>Загрузка…</title>",
            f'<div id="app"></div><script src="/app.js" data-path="{path}"></script>',
        )
    )


async def section(request: Request) -> Response:
    index = await answer(request, "section")
    if index is None or kind_of(index) == "feed":
        return PlainTextResponse("not found", status_code=404)
    if kind_of(index) == "js":
        return scripted("/api/news")
    items = published(index, PAGE_ITEMS)
    tag = etag(items)
    if (unchanged := not_modified(request, index, tag)) is not None:
        return unchanged
    headers = {"ETag": tag} if index % 2 == 0 else {}
    html = page_shell(f"<title>Новости {index}</title>", listing_html(index, items))
    return HTMLResponse(html, headers=headers)


async def article(request: Request) -> Response:
    index = await answer(request, "article")
    number = int(request.path_params["slug"].split("-", 1)[0])
    if index is None:
        return PlainTextResponse("not found", status_code=404)
    if kind_of(index) == "js":
        return scripted(f"/api/news/{number}")
    moment = item(index, number)
    if moment is None:
        return PlainTextResponse("not found", status_code=404)
    head = (
        f"<title>{title(index, number)}</title>"
        f'<meta property="article:published_time" content="{moment.isoformat()}">'
    )
    return HTMLResponse(page_shell(head, article_html(index, number, moment)))


async def api(request: Request) -> Response:
    """What the script draws: the section or an article, as HTML to insert."""
    index = await answer(request, "api")
    if index is None or kind_of(index) != "js":
        return JSONResponse({"html": ""}, status_code=404)
    number = request.path_params.get("number")
    if number is None:
        return JSONResponse({"html": listing_html(index, published(index, PAGE_ITEMS))})
    moment = item(index, int(number))
    if moment is None:
        return JSONResponse({"html": ""}, status_code=404)
    return JSONResponse({"html": article_html(index, int(number), moment)})


APP_JS = """
(function () {
  var path = document.currentScript.getAttribute('data-path');
  setTimeout(function () {
    fetch(path).then(function (r) { return r.json(); }).then(function (data) {
      document.getElementById('app').innerHTML = data.html;
      var h = document.querySelector('h1');
      if (h) { document.title = h.textContent; }
    });
  }, FROM + Math.random() * SPREAD);
})();
""".replace("FROM", str(int(DRAW_DELAY[0] * 1000))).replace(
    "SPREAD", str(int((DRAW_DELAY[1] - DRAW_DELAY[0]) * 1000))
)


async def app_js(request: Request) -> Response:
    await answer(request, "script")
    return Response(APP_JS, media_type="application/javascript")


async def robots(request: Request) -> Response:
    await answer(request, "robots")
    return PlainTextResponse("User-agent: *\nAllow: /\n")


async def tick(request: Request) -> Response:
    minutes = float(request.query_params.get("minutes", "15"))
    CLOCK.shift += timedelta(minutes=minutes)
    due = sum(published(i, 1)[0][0] + 1 for i in range(FEEDS + PAGES + SCRIPTED) if published(i, 1))
    return JSONResponse({"now": CLOCK.now().isoformat(), "published": due})


async def stats(_: Request) -> Response:
    return JSONResponse(dict(sorted(STATS.items())))


async def sources(_: Request) -> Response:
    """The sources to add to the stack: (slug, url, kind, full text)."""
    found = []
    for index in range(FEEDS + PAGES + SCRIPTED):
        kind = kind_of(index)
        base = f"http://{host_of(index)}"
        found.append(
            {
                "slug": f"load-{index + 1:03d}",
                "name": f"Нагрузка {index + 1:03d} ({kind})",
                "url": f"{base}/feed.xml" if kind == "feed" else f"{base}/news",
                "site": base,
                "kind": "rss" if kind == "feed" else "page",
                "full_text": kind == "feed" and index % 2 == 1,
                "farm_kind": kind,
            }
        )
    return Response(json.dumps(found, ensure_ascii=False), media_type="application/json")


app = Starlette(
    routes=[
        Route("/feed.xml", feed),
        Route("/news", section),
        Route("/news/{slug}", article),
        Route("/api/news", api),
        Route("/api/news/{number:int}", api),
        Route("/app.js", app_js),
        Route("/robots.txt", robots),
        Route("/_farm/tick", tick, methods=["POST"]),
        Route("/_farm/stats", stats),
        Route("/_farm/sources", sources),
    ]
)
