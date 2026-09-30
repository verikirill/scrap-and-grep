"""Turn an uploaded resume into text.

Two parsers behind one call. The docling service understands page layout
(two-column resumes read in the right order), runs OCR on scans and accepts
slides, HTML and images. The built-in parser needs no model: it reads the
text layer of a PDF, DOCX and plain text, and takes over when the service is
not configured or not answering.
"""

import asyncio
import contextlib
import html
import io
import multiprocessing
import re
import sys
from dataclasses import dataclass
from multiprocessing.connection import Connection
from typing import Any

import httpx
from docx import Document
from docx.oxml.ns import qn
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from radar.logging import get_logger
from radar.resume.files import BUILTIN_FORMATS, decode_text
from radar.resume.model import ResumeError
from radar.text import strip_html

log = get_logger(__name__)

PARSER_BUILTIN = "builtin"
PARSER_DOCLING = "docling"
# Less text than this in a PDF means a scan: the pages are pictures.
_MIN_PDF_TEXT = 200
_BUILTIN_TIMEOUT = 60.0
_CHILD_MEMORY_BYTES = 1_500_000_000
# Markdown escapes a literal "_" or "*" with a backslash ("t.me/ivan\_p").
_MARKDOWN_ESCAPE_RE = re.compile(r"\\([_*#\[\]()~`>+\-.!|&<])")


def _plain(markdown: str) -> str:
    """Undo Markdown and HTML escaping, so "AT&amp;T" reads "AT&T" again."""
    return html.unescape(_MARKDOWN_ESCAPE_RE.sub(r"\1", markdown))


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    text: str
    parser: str


def _pdf_text(data: bytes, max_pages: int) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ResumeError("PDF защищён паролем. Загрузите файл без защиты.")
        pages = [page.extract_text() or "" for page in reader.pages[:max_pages]]
    except PyPdfError as exc:
        raise ResumeError("PDF повреждён и не читается.") from exc
    text = "\n\n".join(pages).strip()
    if len(text) < _MIN_PDF_TEXT:
        raise ResumeError(
            "В PDF нет текстового слоя: похоже, это скан. Его читает только docling с "
            "распознаванием текста; загрузите DOCX или PDF, сохранённый из редактора."
        )
    return text


def _docx_text(data: bytes) -> str:
    """Every paragraph in document order, including tables and text boxes.

    Resumes are often laid out with tables or floating boxes, which
    `Document.paragraphs` skips.
    """
    try:
        body = Document(io.BytesIO(data)).element.body
    except Exception as exc:  # python-docx raises several unrelated types
        raise ResumeError("DOCX повреждён и не открывается.") from exc
    paragraph_tag, text_tag = qn("w:p"), qn("w:t")
    # Keyed by the paragraph element itself: holding it keeps the lxml proxy
    # alive, so two paragraphs can never be confused.
    lines: dict[Any, list[str]] = {}
    for node in body.iter(text_tag):
        # A text box sits inside a paragraph and holds paragraphs of its own;
        # each run belongs to the nearest one.
        owner = next(node.iterancestors(paragraph_tag), None)
        lines.setdefault(owner, []).append(node.text or "")
    return "\n".join(line for parts in lines.values() if (line := "".join(parts).strip()))


def _parse_builtin(data: bytes, file_format: str, max_pages: int) -> str:
    if file_format == "pdf":
        return _pdf_text(data, max_pages)
    if file_format == "docx":
        return _docx_text(data)
    text = decode_text(data)
    if text is None:
        raise ResumeError("Текст в файле не читается.")
    return strip_html(text) if file_format == "html" else text


class ParserUnavailableError(Exception):
    """The docling service did not answer. Worth a retry, not a verdict on the file."""


def _child(sender: Connection, data: bytes, file_format: str, max_pages: int) -> None:
    """Entry point of the throwaway parser process."""
    if sys.platform != "win32":
        import resource

        # A hostile document must not take the whole machine's memory.
        with contextlib.suppress(ValueError, OSError):
            resource.setrlimit(resource.RLIMIT_AS, (_CHILD_MEMORY_BYTES, _CHILD_MEMORY_BYTES))
    try:
        sender.send(("ok", _parse_builtin(data, file_format, max_pages)))
    except ResumeError as exc:
        sender.send(("rejected", str(exc)))
    except Exception as exc:
        sender.send(("failed", type(exc).__name__))
    finally:
        sender.close()


def _parse_isolated(data: bytes, file_format: str, max_pages: int, timeout: float) -> str:
    """Run the built-in parser in a separate process that can be killed.

    A thread cannot be stopped: a crafted PDF could keep pypdf busy for
    minutes after the caller gave up. A process is killed when the time is up.
    """
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_child, args=(sender, data, file_format, max_pages))
    process.start()
    sender.close()
    try:
        if not receiver.poll(timeout):
            raise ResumeError("Файл разбирается слишком долго. Попробуйте другой формат.")
        outcome, value = receiver.recv()
    except EOFError as exc:
        # The process died without an answer, e.g. on the memory limit.
        raise ResumeError("Файл не удалось разобрать.") from exc
    finally:
        if process.is_alive():
            process.kill()
        process.join(5)
        receiver.close()
    if outcome == "rejected":
        raise ResumeError(value)
    if outcome == "failed":
        raise ResumeError("Файл не удалось разобрать.")
    return str(value)


async def parse_builtin(data: bytes, file_format: str, max_pages: int) -> ParsedDocument:
    if file_format not in (*BUILTIN_FORMATS, "html"):
        raise ResumeError(
            f"Формат {file_format.upper()} читает только сервис docling, а он не подключён. "
            "Загрузите PDF, DOCX или текстовый файл."
        )
    text = await asyncio.to_thread(_parse_isolated, data, file_format, max_pages, _BUILTIN_TIMEOUT)
    return ParsedDocument(text=text, parser=PARSER_BUILTIN)


async def parse_docling(
    client: httpx.AsyncClient, base_url: str, data: bytes, file_format: str, max_pages: int
) -> ParsedDocument:
    """Ask the docling service. It gets the bytes and a format, never a file name."""
    response = await client.post(
        f"{base_url.rstrip('/')}/v1/convert",
        params={"format": file_format, "max_pages": max_pages},
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )
    if response.status_code == httpx.codes.UNPROCESSABLE_ENTITY:
        # The service read the file and could not make sense of it; another
        # parser will not do better, and the reason is worth showing.
        raise ResumeError(str(response.json().get("detail", "Документ не удалось разобрать.")))
    response.raise_for_status()
    return ParsedDocument(text=_plain(str(response.json()["markdown"])), parser=PARSER_DOCLING)


async def parse_document(
    data: bytes,
    file_format: str,
    *,
    docparser_url: str,
    request_timeout: float,
    max_pages: int,
) -> ParsedDocument:
    """Parse with docling when it is configured and answers, otherwise locally.

    When docling is down, formats the built-in parser reads are parsed at
    once; for the others (scans, slides) `ParserUnavailableError` asks the
    queue to try again later instead of failing the upload for good.
    """
    if docparser_url:
        try:
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                return await parse_docling(client, docparser_url, data, file_format, max_pages)
        except httpx.HTTPError as exc:
            log.warning("docparser_unavailable", error=type(exc).__name__)
            if file_format not in (*BUILTIN_FORMATS, "html"):
                raise ParserUnavailableError(type(exc).__name__) from exc
    return await parse_builtin(data, file_format, max_pages)
