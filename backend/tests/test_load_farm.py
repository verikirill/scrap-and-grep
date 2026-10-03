"""scripts/load_farm.py: the sites of the load test (Т6) read as real ones would.

If ingestion stopped finding the farm's links, or stopped taking its script
pages for applications, the load test would measure errors, not reading.
"""

import importlib.util
import re
import sys
from datetime import timedelta
from pathlib import Path
from types import ModuleType

import feedparser
import httpx
from starlette.testclient import TestClient

from radar.ingest.feeds import parse_entries
from radar.ingest.fetch import JS_SHELL, refusal
from radar.ingest.listing import find_links


def _farm() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "load_farm.py"
    spec = importlib.util.spec_from_file_location("load_farm", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


farm = _farm()
FEED, PAGE, SCRIPTED = "s002.farm", f"s{farm.FEEDS + 1:03d}.farm", f"s{farm.FEEDS + 31:03d}.farm"


def _get(client: TestClient, host: str, path: str, **headers: str) -> httpx.Response:
    return client.get(path, headers={"host": host, **headers})


def test_a_feed_is_a_feed_and_says_when_it_has_not_changed() -> None:
    client = TestClient(farm.app)
    first = _get(client, "s001.farm", "/feed.xml")
    items = parse_entries(feedparser.parse(first.content).entries, "ru")
    assert len(items) == farm.FEED_ITEMS
    again = _get(client, "s001.farm", "/feed.xml", **{"if-none-match": first.headers["etag"]})
    assert again.status_code == 304
    article = _get(client, "s001.farm", httpx.URL(items[0].url).path)
    assert article.status_code == 200
    assert refusal(article, "article") is None


def test_a_news_page_has_twenty_links_ingestion_finds() -> None:
    client = TestClient(farm.app)
    page = _get(client, PAGE, "/news")
    links = find_links(page.text, f"http://{PAGE}/news")
    assert len(links) == farm.PAGE_ITEMS
    assert all(link.published_at is not None for link in links)
    assert _get(client, PAGE, httpx.URL(links[0].url).path).status_code == 200


def test_a_script_page_is_an_application_until_drawn() -> None:
    client = TestClient(farm.app)
    for path in ("/news", "/news/3-novost-ob-ugroze"):
        shell = _get(client, SCRIPTED, path)
        assert refusal(shell, "page") == JS_SHELL
    drawn = _get(client, SCRIPTED, "/api/news").json()["html"]
    assert len(find_links(drawn, f"http://{SCRIPTED}/news")) == farm.PAGE_ITEMS


def test_sources_publish_at_the_rates_of_the_snapshot() -> None:
    client = TestClient(farm.app)
    sources = client.get("/_farm/sources").json()
    assert len(sources) == farm.FEEDS + farm.PAGES + farm.SCRIPTED
    assert {item["farm_kind"] for item in sources} == {"feed", "page", "js"}
    newest = {i: farm.published(i, 1)[0][0] for i in range(len(sources))}
    farm.CLOCK.shift += timedelta(days=1)
    try:
        per_day = sum(farm.published(i, 1)[0][0] - newest[i] for i in range(len(sources)))
    finally:
        farm.CLOCK.shift -= timedelta(days=1)
    # 3.4 a day per source on average, give or take the rounding of each.
    assert 2.8 * len(sources) <= per_day <= 3.8 * len(sources)


def test_an_item_not_out_yet_is_not_found() -> None:
    client = TestClient(farm.app)
    newest = farm.published(farm.FEEDS, 1)[0][0]
    assert _get(client, PAGE, f"/news/{newest + 5}-novost-ob-ugroze").status_code == 404
    assert re.search(r"<time", _get(client, PAGE, f"/news/{newest}-x").text)
