"""The pictures of sources: where they are looked for and what is kept."""

from io import BytesIO

from PIL import Image

from radar.db.models import Source
from radar.ingest.avatars import SIZE, icons_in, page_for, square


def _png(size: int) -> bytes:
    output = BytesIO()
    Image.new("RGB", (size, size), (200, 30, 30)).save(output, format="PNG")
    return output.getvalue()


def _ico(*sizes: int) -> bytes:
    output = BytesIO()
    Image.new("RGB", (max(sizes), max(sizes)), (30, 30, 200)).save(
        output, format="ICO", sizes=[(size, size) for size in sizes]
    )
    return output.getvalue()


def test_a_channel_is_asked_on_its_page_and_a_habr_company_on_its_own_site() -> None:
    channel = Source(kind="telegram", feed_url="https://t.me/s/true_secator", site_url=None)
    company = Source(
        kind="rss",
        feed_url="https://habr.com/ru/rss/companies/pt/articles/",
        site_url="https://habr.com/ru/companies/pt/",
    )
    site = Source(kind="rss", feed_url="https://xakep.ru/feed/", site_url="https://xakep.ru")

    assert page_for(channel) == "https://t.me/true_secator"
    assert page_for(company) == "https://ptsecurity.com"
    assert page_for(site) == "https://xakep.ru"


def test_the_largest_raster_icon_comes_first_and_svg_or_inline_ones_are_skipped() -> None:
    page = """
        <link rel="icon" href="data:,">
        <link rel="icon" type="image/svg+xml" href="/icon.svg">
        <link rel="icon" sizes="32x32" href="/favicon-32.png">
        <link rel="apple-touch-icon" sizes="180x180" href="/touch.png">
    """

    found = icons_in(page, "https://example.org/blog/")

    assert found[:2] == ["https://example.org/touch.png", "https://example.org/favicon-32.png"]
    assert found[-2:] == [
        "https://example.org/apple-touch-icon.png",
        "https://example.org/favicon.ico",
    ]
    assert not any(url.endswith(".svg") or url.startswith("data:") for url in found)


def test_a_channel_page_gives_its_avatar_first() -> None:
    page = '<meta property="og:image" content="https://cdn4.telesco.pe/file/avatar.jpg">'

    assert icons_in(page, "https://t.me/alukatsky")[0] == "https://cdn4.telesco.pe/file/avatar.jpg"


def test_a_picture_becomes_a_square_and_a_too_small_one_or_a_non_picture_is_dropped() -> None:
    kept = square(_png(180))
    small = square(_png(16))

    assert kept is not None
    assert Image.open(BytesIO(kept[0])).size == (SIZE, SIZE)
    assert kept[1] == 180
    # A 16-pixel favicon is kept, doubled without blending.
    assert small is not None
    assert small[1] == 16
    assert square(_png(8)) is None
    assert square(b"<html>not a picture</html>") is None


def test_an_ico_gives_its_largest_size() -> None:
    picture = square(_ico(16, 48))

    assert picture is not None
    assert picture[1] == 48
