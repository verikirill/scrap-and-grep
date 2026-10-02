"""The default catalogue: every source is read the way its kind says."""

from typing import get_args

from radar.domain import SourceKind
from radar.ingest import telegram, wordpress
from radar.seed import DEFAULT_SOURCES, SOURCE_KINDS


def test_kinds_name_only_sources_of_the_catalogue() -> None:
    # A slug mistyped here would quietly poll a news page as if it were a feed.
    slugs = {slug for slug, *_ in DEFAULT_SOURCES}

    assert set(SOURCE_KINDS) <= slugs
    assert set(SOURCE_KINDS.values()) <= set(get_args(SourceKind))
    assert len(slugs) == len(DEFAULT_SOURCES)


def test_each_source_has_an_address_its_reader_takes() -> None:
    for slug, _, feed, *_ in DEFAULT_SOURCES:
        kind = SOURCE_KINDS.get(slug, "rss")
        if kind == "wordpress":
            assert wordpress.is_posts_url(feed), slug
        elif kind == "telegram":
            assert telegram.parse_channel(feed), slug
        else:
            assert feed.startswith("https://"), slug
