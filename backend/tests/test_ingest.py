"""Ingestion: what gets stored from a feed, and what the fetcher refuses to touch."""

from datetime import UTC, datetime, timedelta

import feedparser
import pytest

from radar.ingest.feeds import parse_entries
from radar.ingest.net import UnsafeUrlError, _pinned, ensure_public_url
from radar.text import canonical_url, content_hash

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title>
<item>
  <title>Уязвимость в &lt;b&gt;SCADA&lt;/b&gt;</title>
  <link>https://www.example.org/news/1/?utm_source=rss&amp;id=7#comments</link>
  <description>&lt;p&gt;Короткий анонс.&lt;/p&gt;</description>
  <pubDate>Tue, 29 Sep 2026 10:00:00 +0300</pubDate>
  <category>ICS</category>
</item>
<item>
  <title>Дубль той же новости</title>
  <link>https://example.org/news/1?id=7</link>
  <pubDate>Tue, 29 Sep 2026 11:00:00 +0300</pubDate>
</item>
<item>
  <title>Бюллетень с полным текстом</title>
  <link>https://example.org/advisory/2</link>
  <description>{long_text}</description>
  <pubDate>Tue, 29 Sep 2026 12:00:00 +0300</pubDate>
</item>
<item>
  <title>Запись из будущего</title>
  <link>https://example.org/news/3</link>
  <pubDate>Fri, 01 Jan 2100 00:00:00 +0000</pubDate>
</item>
<item>
  <title>Ссылка не по http</title>
  <link>javascript:alert(1)</link>
</item>
<item><link>https://example.org/no-title</link></item>
</channel></rss>
""".format(long_text="Описание уязвимости и меры защиты. " * 80)


def test_tracking_parameters_and_fragments_do_not_create_new_urls() -> None:
    plain = canonical_url("https://example.org/news/1?id=7")
    noisy = canonical_url("https://WWW.Example.org/news/1/?utm_source=rss&id=7&fbclid=x#comments")

    assert noisy == plain


def test_content_hash_ignores_markup_case_and_spacing() -> None:
    assert content_hash("Критическая  уязвимость", "в Chrome!") == content_hash(
        "критическая уязвимость", "В   CHROME"
    )


def test_feed_entries_become_clean_deduplicated_articles() -> None:
    entries = feedparser.parse(FEED).entries

    articles = parse_entries(entries, "ru")

    by_url = {article.url: article for article in articles}
    assert set(by_url) == {
        "https://example.org/news/1?id=7",
        "https://example.org/advisory/2",
        "https://example.org/news/3",
    }
    first = by_url["https://example.org/news/1?id=7"]
    assert first.title == "Уязвимость в SCADA"
    assert first.summary == "Короткий анонс."
    assert first.content is None
    assert first.tags == ("ICS",)
    assert first.published_at == datetime(2026, 9, 29, 7, 0, tzinfo=UTC)


def test_long_description_is_kept_as_full_text_with_a_short_teaser() -> None:
    entries = feedparser.parse(FEED).entries

    advisory = next(a for a in parse_entries(entries, "en") if a.url.endswith("/advisory/2"))

    assert advisory.content is not None
    assert len(advisory.content) > 2000
    assert len(advisory.summary) <= 1501


def test_future_publication_date_is_clamped_to_now() -> None:
    entries = feedparser.parse(FEED).entries

    future = next(a for a in parse_entries(entries, "ru") if a.url.endswith("/news/3"))

    assert future.published_at <= datetime.now(UTC) + timedelta(seconds=5)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:5432/",
        "http://localhost/feed",
        "http://10.0.0.5/rss",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/feed",
        "file:///etc/passwd",
        "ftp://example.org/feed",
    ],
)
async def test_fetcher_refuses_internal_and_non_http_addresses(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        await ensure_public_url(url)


def test_pinned_request_keeps_the_host_name_for_routing_and_tls() -> None:
    target, headers, extensions = _pinned("https://пример.рф/rss?page=2", "93.184.216.34")

    assert target == "https://93.184.216.34/rss?page=2"
    assert headers == {"Host": "xn--e1afmkfd.xn--p1ai"}
    assert extensions == {"sni_hostname": "xn--e1afmkfd.xn--p1ai"}


def test_pinned_request_brackets_ipv6_and_keeps_the_port() -> None:
    target, headers, _ = _pinned("http://feeds.example.org:8080/a", "2001:db8::7")

    assert target == "http://[2001:db8::7]:8080/a"
    assert headers == {"Host": "feeds.example.org:8080"}
