# ruff: noqa: F811  (the fixtures are imported from the other tests)
"""Symantec's protection bulletins: the JSON the bulletin page is drawn from,
read into articles, the newest first."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from radar.ingest import broadcom
from radar.ingest.fetch import Ladder
from radar.ingest.pages import MarkupChanged
from tests.test_telegram import offline  # noqa: F401

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
# The answer of /api/nocache/mblogs?limit=2 of October 3, 2026, texts cut short.
ANSWER: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "broadcom" / "mblogs.json").read_text(encoding="utf-8")
)


def test_the_newest_bulletins_of_every_year_newest_first() -> None:
    articles = broadcom.parse_bulletins(ANSWER, NOW)

    assert [article.published_at.date().isoformat() for article in articles] == [
        "2026-10-02",
        "2026-10-02",
        "2025-12-29",
        "2025-12-24",
        "2020-12-31",
        "2020-12-30",
    ]
    first = articles[0]
    assert first.title == "Vidar and Remus infostealers distributed with help of new 2CLoader"
    assert first.url == (
        "https://broadcom.com/support/security-center/protection-bulletin/"
        "vidar-and-remus-infostealers-distributed-with-help-of-new-2cloader"
    )
    assert first.language == "en"
    assert first.tags == (broadcom.TAG,)
    # The bulletin is all there is: its text is stored whole, without markup.
    assert first.content is not None
    assert "<p>" not in first.content
    assert first.summary.startswith(first.content[:40])


def test_a_bulletin_without_a_page_gets_an_address_of_its_own() -> None:
    articles = broadcom.parse_bulletins(ANSWER, NOW)
    bella = next(article for article in articles if "Bella" in article.title)

    assert bella.url == (
        "https://broadcom.com/support/security-center/protection-bulletin?id=1211260755767"
    )
    assert len({article.url for article in articles}) == len(articles)


def test_only_twenty_are_taken_and_a_highlight_is_tagged() -> None:
    many = {
        "2026": [
            {
                "content_id": str(day),
                "title": f"Bulletin {day}",
                "published": f"September {day:02d}, 2026",
                "body": "<p>Coverage is in place.</p>",
                "highlight": "Yes" if day == 30 else "No",
                "url": f"/support/security-center/protection-bulletin/bulletin-{day}",
            }
            for day in range(1, 31)
        ]
    }
    articles = broadcom.parse_bulletins(many, NOW)

    assert len(articles) == broadcom.NEWEST
    assert articles[0].title == "Bulletin 30"
    assert articles[0].tags == (broadcom.TAG, broadcom.HIGHLIGHT_TAG)
    assert articles[-1].title == "Bulletin 11"


@pytest.mark.parametrize(
    "answer",
    [[], {"2026": [{"title": "no date", "published": "soon"}]}],
)
def test_an_answer_of_another_shape_is_a_changed_markup(answer: Any) -> None:
    with pytest.raises(MarkupChanged):
        broadcom.parse_bulletins(answer, NOW)


async def test_the_bulletins_through_the_ladder(offline: None) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.params["limit"] == "20"
        return httpx.Response(200, json=ANSWER, request=request)

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client,
        Ladder(client) as ladder,
    ):
        feed = await broadcom.fetch_bulletins(ladder, broadcom.API, etag=None, last_modified=None)

    assert feed.status == "ok"
    assert len(feed.articles) == 6
