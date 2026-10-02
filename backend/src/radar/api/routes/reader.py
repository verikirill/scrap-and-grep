"""An article opened in the app: its text and pictures, as its page has them."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from radar.api.deps import CacheDep, SessionDep, current_user, user_rate_limit
from radar.api.schemas import ArticleReadOut
from radar.db.models import Article
from radar.images.store import get_image_store
from radar.logging import get_logger
from radar.reader import service as reader
from radar.reading import reading_minutes

router = APIRouter(tags=["reader"], dependencies=[Depends(current_user)])
log = get_logger(__name__)

# Opening an article may read its page; a reader opens a few a minute, not hundreds.
_read_limit = Depends(user_rate_limit("read", lambda settings: settings.rate_limit_per_minute))
# A page of the reader shows up to 40 pictures, each a request of its own.
_picture_limit = Depends(
    user_rate_limit("pictures", lambda settings: settings.picture_rate_limit_per_minute)
)
# A picture's path holds a hash of its address: what it serves never changes.
_PICTURE_HEADERS = {
    "Cache-Control": "private, max-age=2592000, immutable",
    "Content-Security-Policy": "default-src 'none'",
}


@router.get("/articles/{article_id}", dependencies=[_read_limit])
async def read_article(article_id: int, session: SessionDep) -> ArticleReadOut:
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Статья не найдена.")
    reading = await reader.open_article(session, article)
    return ArticleReadOut(
        id=article.id,
        url=article.url,
        title=article.title,
        author=article.author,
        source_id=article.source_id,
        source_name=article.source.name,
        source_category=article.source.category,
        language=article.language,
        tags=article.tags,
        published_at=article.published_at,
        reading_minutes=reading_minutes(article.word_count, article.language),
        complete=reading.complete,
        blocks=reading.blocks,
    )


@router.get("/articles/{article_id}/picture", dependencies=[_picture_limit])
async def article_picture(article_id: int, session: SessionDep, cache: CacheDep) -> Response:
    """The article's own picture, for a post in the feed."""
    try:
        found = await reader.lead_picture(session, article_id, get_image_store(), cache)
    except reader.PictureUnavailable as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Сайт не отдал картинку.") from exc
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="У статьи нет картинки.")
    # A stale address is replaced by the one the page gives now: a day, not for good.
    return Response(
        content=found.data,
        media_type=found.content_type,
        headers={**_PICTURE_HEADERS, "Cache-Control": "private, max-age=86400"},
    )


@router.get("/articles/{article_id}/images/{name}", dependencies=[_picture_limit])
async def article_image(
    article_id: int,
    name: Annotated[str, Path(pattern=r"^[0-9a-f]{16}$")],
    session: SessionDep,
    cache: CacheDep,
) -> Response:
    try:
        found = await reader.picture(session, article_id, name, get_image_store(), cache)
    except reader.PictureUnavailable as exc:
        error = type(exc.__cause__).__name__ if exc.__cause__ else "refused_recently"
        log.info("reader_picture_failed", article_id=article_id, error=error)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Сайт не отдал картинку.") from exc
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Картинки нет в статье.")
    return Response(content=found.data, media_type=found.content_type, headers=_PICTURE_HEADERS)
