"""An English or Chinese article in Russian, translated by the model for the reader.

Only words travel to the model. The blocks keep their kinds and their order:
a headline, a heading, a paragraph, a list item, a quote, a picture's caption
and a table cell are each a fragment of their own, code is never sent, and
the links and marks of a paragraph go as numbered tags around its words, their
addresses staying here. An answer that loses a fragment, a tag, an identifier
or a number is asked for again once; a fragment broken twice keeps its original
words. One such paragraph among many is no reason to show the reader nothing:
the article is refused whole, and shown in the original, only when more than a
fifth of its fragments, and at least two, stayed untranslated.
"""

import asyncio
import json
import re
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol, cast

import structlog
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.ai.prompts import (
    TRANSLATION_PROMPT_VERSION,
    TranslationOut,
    translation_prompt,
    translation_system,
)
from radar.ai.resilient import CircuitBreaker
from radar.cache import Cache
from radar.db.models import ArticleTranslation
from radar.logging import get_logger
from radar.reader.blocks import Block, Paragraph, Quote, Span
from radar.reader.language import Language, detect
from radar.text import numbers, stable_hash

log = get_logger(__name__)

TARGET = "ru"
# Characters of fragments in one request. Russian comes out a fifth longer and
# costs more tokens than English: 5 000 in keep the answer well inside 8k context.
BATCH_CHARS = 5000
BATCH_PIECES = 40
# Twelve requests at most; a longer text is a document, not news.
MAX_CHARS = 60_000
# A text the model would not translate faithfully is not asked again for this long.
REFUSED_RETRY_SECONDS = 3600
# Two answers per batch: the first and one with its mistakes named.
_ATTEMPTS = 2
# Fragments the model broke twice stay in the original; more than this share of
# them, and at least this many, and the article is not called translated.
KEPT_SHARE = 0.2
KEPT_AT_LEAST = 2

_TAG = re.compile(r"<(\d+)>(.*?)</\1>", re.DOTALL)
_ANY_TAG = re.compile(r"</?\d+>")
# What a translation keeps as written: identifiers and addresses.
_KEPT = re.compile(
    r"\b(?:CVE-\d{4}-\d{4,7}|BDU:\d{4}-\d{5}|GHSA(?:-[0-9a-z]{4}){3}|KB\d{6,8})\b"
    r"|https?://[^\s<>\"']+",
    re.IGNORECASE,
)
# "1,000" in English is "1 000" in Russian; numbers() reads the comma as a decimal one.
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")

NO_MODEL = "Перевод делает языковая модель, а сервис сейчас работает без неё."
NOT_NOW = "Модель сейчас не смогла перевести статью. Попробуйте открыть её позже."
TOO_LONG = "Статья слишком длинная для перевода."
UNSUPPORTED = "Перевод с этого языка пока не поддерживается."


class Chat(Protocol):
    name: str

    async def ask[T: BaseModel](self, schema: type[T], system: str, user: str) -> T: ...


class TranslationRefused(Exception):
    """The model answered, but its answer does not keep the article."""


class TooLong(Exception):
    """More text than the reader translates."""


@dataclass(frozen=True, slots=True)
class Translation:
    title: str
    blocks: list[Block]
    # Fragments left in the original language: the model broke them twice.
    kept_original: int = 0


@dataclass(frozen=True, slots=True)
class Unavailable:
    reason: str


@dataclass(frozen=True, slots=True)
class _Piece:
    # As sent: the marked spans of a paragraph in numbered tags.
    text: str
    # The spans it was made of; None for a plain string (a heading, a cell).
    spans: tuple[Span, ...] | None


type _Done = str | list[Span]


@dataclass(frozen=True, slots=True)
class _Answered:
    done: dict[int, _Done]
    # The fragments the model broke twice, with what was wrong the second time.
    failed: dict[int, str]


class _Visitor(Protocol):
    def text(self, value: str) -> str: ...

    def spans(self, value: list[Span]) -> list[Span]: ...


def _walk(title: str, blocks: Sequence[Block], visit: _Visitor) -> Translation:
    """The article with every fragment passed through `visit`, in reading order."""
    new_title = visit.text(title)
    out: list[Block] = []
    for block in blocks:
        if block["type"] == "p":
            out.append(Paragraph(type="p", spans=visit.spans(block["spans"])))
        elif block["type"] == "quote":
            out.append(Quote(type="quote", spans=visit.spans(block["spans"])))
        elif block["type"] == "h":
            out.append({**block, "text": visit.text(block["text"])})
        elif block["type"] == "list":
            out.append({**block, "items": [visit.spans(item) for item in block["items"]]})
        elif block["type"] == "image" and "alt" in block:
            out.append({**block, "alt": visit.text(block["alt"])})
        elif block["type"] == "table":
            head = [visit.text(cell) for cell in block["head"]] if block["head"] else block["head"]
            rows = [[visit.text(cell) for cell in row] for row in block["rows"]]
            out.append({**block, "head": head, "rows": rows})
        else:
            out.append(block)
    return Translation(new_title, out)


def _is_marked(span: Span) -> bool:
    return any(key in span for key in ("b", "i", "code", "href"))


def _encoded(spans: Sequence[Span]) -> str:
    parts: list[str] = []
    number = 0
    for span in spans:
        if _is_marked(span):
            number += 1
            parts.append(f"<{number}>{span['text']}</{number}>")
        else:
            parts.append(span["text"])
    return "".join(parts)


class _Collect:
    def __init__(self) -> None:
        self.pieces: list[_Piece] = []

    def text(self, value: str) -> str:
        self.pieces.append(_Piece(value, None))
        return value

    def spans(self, value: list[Span]) -> list[Span]:
        self.pieces.append(_Piece(_encoded(value), tuple(value)))
        return value


class _Replace:
    def __init__(self, done: Iterator[_Done]) -> None:
        self._done = done

    def text(self, value: str) -> str:
        found = next(self._done)
        return found if isinstance(found, str) else value

    def spans(self, value: list[Span]) -> list[Span]:
        found = next(self._done)
        return found if isinstance(found, list) else value


def _pieces(title: str, blocks: Sequence[Block]) -> list[_Piece]:
    collect = _Collect()
    _walk(title, blocks, collect)
    return collect.pieces


def _is_worth(piece: _Piece) -> bool:
    """A fragment with words to translate: not Russian, not only an address or a number."""
    words = _KEPT.sub(" ", _ANY_TAG.sub("", piece.text))
    return detect(words) != "ru"


def _decoded(answer: str, spans: Sequence[Span]) -> tuple[list[Span], str | None]:
    """The translated paragraph back as spans, each tag with the marks of its span."""
    marked = [span for span in spans if _is_marked(span)]
    out: list[Span] = []
    seen: set[int] = set()
    position = 0
    for match in _TAG.finditer(answer):
        out.extend(_plain(answer[position : match.start()]))
        number = int(match.group(1))
        if not 1 <= number <= len(marked) or number in seen:
            return [], f"лишний тег <{number}>"
        if _ANY_TAG.search(match.group(2)):
            return [], f"тег внутри тега <{number}>"
        seen.add(number)
        span = marked[number - 1].copy()
        # Code inside a sentence stays as written, whatever came back.
        if not span.get("code"):
            span["text"] = match.group(2)
        if not span["text"].strip():
            return [], f"пустой тег <{number}>"
        out.append(span)
        position = match.end()
    out.extend(_plain(answer[position:]))
    if any(_ANY_TAG.search(span["text"]) for span in out if not _is_marked(span)):
        return [], "незакрытый или лишний тег"
    if missing := sorted(set(range(1, len(marked) + 1)) - seen):
        return [], "потеряны теги " + ", ".join(f"<{number}>" for number in missing)
    return out, None


def _plain(text: str) -> list[Span]:
    return [{"text": text}] if text else []


def _lost(source: str, answer: str) -> list[str]:
    """Identifiers, addresses and numbers of the source the answer does not have."""
    source = unicodedata.normalize("NFKC", _ANY_TAG.sub("", source))
    answer = unicodedata.normalize("NFKC", _ANY_TAG.sub("", answer))
    folded = answer.casefold()
    lost = sorted({kept for kept in _KEPT.findall(source) if kept.casefold() not in folded})
    lost += sorted(numbers(_THOUSANDS.sub("", source)) - numbers(answer))
    return lost


def _checked(piece: _Piece, answer: str | None) -> tuple[_Done, str | None]:
    """The fragment's translation, or what is wrong with it."""
    if answer is None or not answer.strip():
        return "", "нет перевода"
    answer = answer.strip()
    if lost := _lost(piece.text, answer):
        return "", "потеряны " + ", ".join(lost[:5])
    if piece.spans is None:
        if _ANY_TAG.search(answer):
            return "", "лишний тег"
        return answer, None
    return _decoded(answer, piece.spans)


def _batches(wanted: Sequence[tuple[int, _Piece]]) -> list[list[tuple[int, _Piece]]]:
    batches: list[list[tuple[int, _Piece]]] = []
    size = 0
    for numbered in wanted:
        length = len(numbered[1].text)
        if not batches or size + length > BATCH_CHARS or len(batches[-1]) >= BATCH_PIECES:
            batches.append([])
            size = 0
        batches[-1].append(numbered)
        size += length
    return batches


async def _batch(chat: Chat, system: str, batch: list[tuple[int, _Piece]]) -> _Answered:
    """What the model translated faithfully, and the fragments it broke twice;
    a failure of the model itself is raised."""
    done: dict[int, _Done] = {}
    pending = batch
    failed: dict[int, str] = {}
    for _ in range(_ATTEMPTS):
        problems = [f"фрагмент {number}: {problem}" for number, problem in failed.items()]
        prompt = translation_prompt([(number, piece.text) for number, piece in pending], problems)
        out = await chat.ask(TranslationOut, system, prompt)
        answers = {item.id: item.text for item in out.items}
        failed, left = {}, []
        for number, piece in pending:
            result, problem = _checked(piece, answers.get(number))
            if problem is None:
                done[number] = result
            else:
                failed[number] = problem
                left.append((number, piece))
        if not left:
            break
        pending = left
    return _Answered(done, failed)


def _too_many_kept(failed: int, translated: int, wanted: int) -> bool:
    """Whether the fragments left in the original make the article a half-translation.
    The headline alone may stay as it was."""
    if not failed:
        return False
    return translated == 0 or (failed >= KEPT_AT_LEAST and failed > KEPT_SHARE * wanted)


async def translate(
    chat: Chat, source: Language, title: str, blocks: Sequence[Block]
) -> Translation:
    """The article in Russian, every block where it was. A fragment the model
    broke twice keeps its original words; too many of them and it raises."""
    pieces = _pieces(title, blocks)
    wanted = [(number, piece) for number, piece in enumerate(pieces) if _is_worth(piece)]
    if sum(len(piece.text) for _, piece in wanted) > MAX_CHARS:
        raise TooLong
    system = translation_system(source)
    done: dict[int, _Done] = {}
    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(_batch(chat, system, batch)) for batch in _batches(wanted)]
    except ExceptionGroup as errors:
        # The first failure of the model is the answer; the others were cancelled with it.
        raise errors.exceptions[0] from None
    failed: dict[int, str] = {}
    for task in tasks:
        answered = task.result()
        done.update(answered.done)
        failed.update(answered.failed)
    problems = "; ".join(f"фрагмент {number}: {failed[number]}" for number in sorted(failed))
    if _too_many_kept(len(failed), len(done), len(wanted)):
        raise TranslationRefused(problems[:500])
    if failed:
        log.info(
            "reader_translation_kept_original",
            fragments=sorted(failed),
            of=len(wanted),
            problems=problems[:300],
        )
    originals: list[_Done] = [list(piece.spans) if piece.spans else piece.text for piece in pieces]
    made = _walk(title, blocks, _Replace(iter(done.get(n, o) for n, o in enumerate(originals))))
    return replace(made, kept_original=len(failed))


def fingerprint(source: Language, title: str, blocks: Sequence[Block]) -> str:
    text = json.dumps([title, blocks], ensure_ascii=False, sort_keys=True)
    return stable_hash(TRANSLATION_PROMPT_VERSION, source, TARGET, text)


async def for_reader(
    session: AsyncSession,
    cache: Cache,
    *,
    article_id: int,
    source: Language,
    title: str,
    blocks: Sequence[Block],
    chat: Chat | None,
    breaker: CircuitBreaker,
) -> Translation | Unavailable:
    """The stored translation, or a new one made and stored for every next reader."""
    if source not in {"en", "zh"}:
        return Unavailable(UNSUPPORTED)
    made_from = fingerprint(source, title, blocks)
    row = await session.get(ArticleTranslation, (article_id, TARGET))
    if row is not None and row.fingerprint == made_from:
        return Translation(row.title, cast(list[Block], row.blocks), row.kept_original)
    if chat is None:
        return Unavailable(NO_MODEL)
    refused = f"reader:translation-refused:{article_id}:{made_from}"
    if not breaker.allow() or await cache.get_json(refused):
        return Unavailable(NOT_NOW)
    # Nothing waits on the database while the model writes.
    await session.commit()
    try:
        with structlog.contextvars.bound_contextvars(article_id=article_id):
            done = await translate(chat, source, title, blocks)
    except TooLong:
        return Unavailable(TOO_LONG)
    except TranslationRefused as exc:
        # The model is up and answered: its mistakes are no reason to stop the digests.
        log.warning("reader_translation_refused", article_id=article_id, problems=str(exc)[:300])
        await cache.set_json(refused, True, REFUSED_RETRY_SECONDS)
        return Unavailable(NOT_NOW)
    except Exception as exc:  # the model server: down, slow, full or answering nonsense
        breaker.record_failure()
        error = f"{type(exc).__name__}: {exc}"[:300]
        log.warning("reader_translation_failed", article_id=article_id, error=error)
        return Unavailable(NOT_NOW)
    breaker.record_success()
    await _store(session, article_id, source, made_from, chat.name, done)
    log.info(
        "reader_translated",
        article_id=article_id,
        source=source,
        model=chat.name,
        kept_original=done.kept_original,
    )
    return done


async def _store(
    session: AsyncSession,
    article_id: int,
    source: Language,
    made_from: str,
    model: str,
    done: Translation,
) -> None:
    values = {
        "source_language": source,
        "fingerprint": made_from,
        "model": model[:200],
        "title": done.title,
        "blocks": done.blocks,
        "kept_original": done.kept_original,
        "translated_at": datetime.now(UTC),
    }
    await session.execute(
        insert(ArticleTranslation)
        .values(article_id=article_id, language=TARGET, **values)
        .on_conflict_do_update(
            index_elements=[ArticleTranslation.article_id, ArticleTranslation.language],
            set_=values,
        )
    )
