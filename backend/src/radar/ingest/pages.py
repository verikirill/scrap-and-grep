"""What an article's page says, read the way the site allows."""

import trafilatura

from radar.ingest import bdu


class MarkupChanged(Exception):
    """A page that should list posts or entries has them, but none could be read."""


def page_text(url: str, page: str) -> str | None:
    """The readable text of the page at `url`, or None when there is none.

    Most pages are read by trafilatura. A BDU vulnerability is drawn in the
    browser from data in the page, so its text comes from that data.
    """
    if bdu.is_vulnerability_page(url):
        return bdu.page_text(page)
    return trafilatura.extract(page, include_comments=False, include_tables=False)
