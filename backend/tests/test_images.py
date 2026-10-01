"""Finding an article's picture: in the feed entry, on the page, by its bytes."""

from pathlib import Path

import feedparser
import pytest

from radar.images.extract import from_entry, from_page, usable
from radar.images.service import image_key, sniff
from radar.images.store import LocalImageStore

FEED = """<?xml version="1.0"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>t</title>
<item><title>media</title><link>https://ex.org/1</link>
  <media:content url="https://cdn.ex.org/1.jpg" medium="image"/></item>
<item><title>enclosure</title><link>https://ex.org/2</link>
  <enclosure url="https://cdn.ex.org/2.png" type="image/png" length="1"/></item>
<item><title>inline</title><link>https://ex.org/3</link>
  <description><![CDATA[<img src="/pixel.gif" width="1"><p>x</p>
  <img src="/img/3.webp">]]></description></item>
<item><title>none</title><link>https://ex.org/4</link><description>text only</description></item>
</channel></rss>"""


def test_a_feed_entry_gives_its_picture_wherever_it_keeps_it() -> None:
    entries = feedparser.parse(FEED).entries

    found = [from_entry(entry, entry.link) for entry in entries]

    assert found == [
        "https://cdn.ex.org/1.jpg",
        "https://cdn.ex.org/2.png",
        # A tracking pixel is not the story's picture; a relative path is resolved.
        "https://ex.org/img/3.webp",
        None,
    ]


def test_a_page_declares_its_picture_in_the_head() -> None:
    page = (
        "<html><head><meta name='twitter:image' content='https://ex.org/tw.jpg'>"
        "<meta property='og:image' content='/og.jpg'></head>"
        "<body><meta property='og:image' content='https://evil.org/late.jpg'></body></html>"
    )

    assert from_page(page, "https://ex.org/news/1") == "https://ex.org/og.jpg"


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:image/png;base64,AAAA",
        "https://ex.org/logo.svg",
        "/favicon.ico",
        "https://www.cnews.ru/img/design2008/placeholderimage.jpg",
        "https://ex.org/static/no-image.png",
    ],
)
def test_not_every_address_is_a_picture_of_the_story(url: str) -> None:
    assert usable(url, "https://ex.org") is None


def test_the_format_is_read_from_the_bytes_not_the_header() -> None:
    assert sniff(b"\xff\xd8\xff\xe0rest") == "jpg"
    assert sniff(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert sniff(b"<html>not a picture") is None


async def test_a_stored_copy_is_found_by_its_key_and_keys_cannot_escape(tmp_path: Path) -> None:
    store = LocalImageStore(tmp_path)
    key = image_key("https://cdn.ex.org/1.jpg", "jpg")

    await store.put(key, b"\xff\xd8\xffdata")

    assert await store.get(key) == b"\xff\xd8\xffdata"
    assert await store.get(image_key("https://other", "jpg")) is None
    with pytest.raises(ValueError, match="key"):
        await store.get("../../etc/passwd")
