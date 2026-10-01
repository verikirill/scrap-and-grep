"""Which pictures go into a video, and that a missing one never stops it."""

from radar.db.models import Article
from radar.images.service import Picture
from radar.shorts.pictures import MAX_PICTURE_BYTES, pictures_for

JPEG = Picture(b"\xff\xd8\xff" + b"\x00" * 64, "jpg")


async def test_each_news_item_gets_its_own_picture_or_none() -> None:
    by_article = {
        1: JPEG,
        2: Picture(b"GIF89a" + b"\x00" * 64, "gif"),
        3: Picture(b"\xff\xd8\xff" + b"\x00" * MAX_PICTURE_BYTES, "jpg"),
        4: None,
    }

    async def fetch(article: Article) -> Picture | None:
        if article.id == 5:
            raise TimeoutError
        return by_article[article.id]

    articles = [Article(id=article_id) for article_id in (1, 2, 3, 4, 5)]

    pictures = await pictures_for([*articles, None], fetch)

    # A GIF would animate on its own clock, a huge picture is refused by the
    # renderer, and a failed download leaves the item without a picture.
    assert pictures == [JPEG, None, None, None, None, None]
