"""An article opened in the app: its text and pictures, as its page has them."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from radar.ai.factory import get_breaker, get_chat
from radar.api.deps import CacheDep, SessionDep, current_user, user_rate_limit
from radar.api.schemas import ArticleReadOut, ArticleTranslationOut
from radar.db.models import Article
from radar.images.store import get_image_store
from radar.logging import get_logger
from radar.reader import service as reader
from radar.reader import translate
from radar.reader.language import article_language
from radar.reading import reading_minutes

router = APIRouter(tags=["reader"], dependencies=[Depends(current_user)])
log = get_logger(__name__)

# Opening an article may read its page; a reader opens a few a minute, not hundreds.
_read_limit = Depends(user_rate_limit("read", lambda settings: settings.rate_limit_per_minute))
# A translation costs the model a minute once; then it is read from the database.
_translate_limit = Depends(
    user_rate_limit("translate", lambda settings: settings.rate_limit_per_minute)
)
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
        text_language=article_language(article.title, reading.blocks, article.source.language),
        blocks=reading.blocks,
    )


@router.get("/articles/{article_id}/translation", dependencies=[_translate_limit])
async def translate_article(
    article_id: int,
    session: SessionDep,
    cache: CacheDep,
    to: Annotated[Literal["ru"], Query()] = "ru",
) -> ArticleTranslationOut:
    """The article in Russian: stored once translated, made by the model on first need."""
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Статья не найдена.")
    title = article.title
    reading = await reader.open_article(session, article)
    source = article_language(title, reading.blocks, article.source.language)
    if source == "ru":
        return ArticleTranslationOut(
            id=article_id, status="original", source_language=source, language=to
        )
    found = await translate.for_reader(
        session,
        cache,
        article_id=article_id,
        source=source,
        title=title,
        blocks=reading.blocks,
        chat=get_chat(),
        breaker=get_breaker(),
    )
    if isinstance(found, translate.Unavailable):
        return ArticleTranslationOut(
            id=article_id,
            status="unavailable",
            source_language=source,
            language=to,
            reason=found.reason,
        )
    return ArticleTranslationOut(
        id=article_id,
        status="translated",
        source_language=source,
        language=to,
        title=found.title,
        blocks=found.blocks,
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
