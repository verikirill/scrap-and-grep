"""HTTP service: a document in, Markdown out.

Stateless and deliberately small. It receives untrusted files, so it knows
nothing else: no database, no credentials, no outbound network. One document
is converted at a time per process; more throughput means more replicas.
"""

import asyncio
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import ConversionStatus, DocumentStream, InputFormat
from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions, TableFormerMode
from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption
from fastapi import FastAPI, HTTPException, Query, Request
from PIL import Image
from pydantic import BaseModel

log = logging.getLogger("docparser")

MAX_BYTES = int(os.environ.get("DOCPARSER_MAX_BYTES", "10000000"))
# A picture of a page needs a few million pixels. A small PNG that declares
# billions of them is a decompression bomb; Pillow refuses it above this.
Image.MAX_IMAGE_PIXELS = 60_000_000
THREADS = int(os.environ.get("DOCPARSER_THREADS", "4"))
OCR_ENABLED = os.environ.get("DOCPARSER_OCR", "true").lower() == "true"
# Set in the image after the models are baked in: nothing is fetched at run time.
OFFLINE = os.environ.get("DOCPARSER_OFFLINE", "false").lower() == "true"
# A resume is a few pages. A document that needs longer is abandoned.
DOCUMENT_TIMEOUT = float(os.environ.get("DOCPARSER_DOCUMENT_TIMEOUT", "150"))
# How long a request may wait for the converter to become free.
QUEUE_TIMEOUT = float(os.environ.get("DOCPARSER_QUEUE_TIMEOUT", "120"))

# Accepted format -> (docling input format, file extension docling detects it by).
FORMATS: dict[str, tuple[InputFormat, str]] = {
    "pdf": (InputFormat.PDF, "pdf"),
    "docx": (InputFormat.DOCX, "docx"),
    "pptx": (InputFormat.PPTX, "pptx"),
    "odt": (InputFormat.ODT, "odt"),
    "html": (InputFormat.HTML, "html"),
    "md": (InputFormat.MD, "md"),
    # Plain text is valid Markdown.
    "txt": (InputFormat.MD, "md"),
    "png": (InputFormat.IMAGE, "png"),
    "jpg": (InputFormat.IMAGE, "jpg"),
}


class Converted(BaseModel):
    markdown: str
    pages: int
    seconds: float


def build_converter() -> DocumentConverter:
    """Layout analysis and table structure on CPU, OCR for Russian and English."""
    options = PdfPipelineOptions()
    options.accelerator_options = AcceleratorOptions(
        num_threads=THREADS, device=AcceleratorDevice.CPU
    )
    options.document_timeout = DOCUMENT_TIMEOUT
    options.do_table_structure = True
    options.table_structure_options.mode = TableFormerMode.FAST
    options.do_ocr = OCR_ENABLED
    if OCR_ENABLED:
        # EasyOCR covers Cyrillic; the default engine ships Chinese and
        # English models only.
        options.ocr_options = EasyOcrOptions(
            lang=["ru", "en"], use_gpu=False, download_enabled=not OFFLINE
        )
    return DocumentConverter(
        allowed_formats=sorted({fmt for fmt, _ in FORMATS.values()}, key=lambda fmt: fmt.value),
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=options),
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    # docling reports every step of every document; the service's own line per
    # request is enough.
    logging.getLogger("docling").setLevel(logging.WARNING)
    converter = build_converter()
    # Load the models now, not on the first upload.
    await asyncio.to_thread(converter.initialize_pipeline, InputFormat.PDF)
    app.state.converter = converter
    app.state.busy = asyncio.Lock()
    log.info("ready threads=%s ocr=%s", THREADS, OCR_ENABLED)
    yield


app = FastAPI(title="Radar docparser", version="0.1.0", lifespan=lifespan, docs_url=None)


async def _read(request: Request) -> bytes:
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > MAX_BYTES:
            raise HTTPException(413, detail="Файл слишком большой.")
        chunks.append(chunk)
    return b"".join(chunks)


def _convert(converter: DocumentConverter, data: bytes, fmt: str, max_pages: int) -> Converted:
    _, extension = FORMATS[fmt]
    started = time.perf_counter()
    result = converter.convert(
        DocumentStream(name=f"document.{extension}", stream=BytesIO(data)),
        raises_on_error=False,
        page_range=(1, max_pages),
    )
    if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
        raise ValueError(f"conversion ended with {result.status.name}")
    markdown = result.document.export_to_markdown().strip()
    return Converted(
        markdown=markdown,
        pages=len(result.pages),
        seconds=round(time.perf_counter() - started, 2),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/convert")
async def convert(
    request: Request,
    fmt: str = Query(alias="format"),
    max_pages: int = Query(default=12, ge=1, le=50),
) -> Converted:
    """Convert the request body. The caller states the format it detected."""
    if fmt not in FORMATS:
        raise HTTPException(415, detail=f"Формат {fmt} не поддерживается.")
    data = await _read(request)
    try:
        async with asyncio.timeout(QUEUE_TIMEOUT):
            await request.app.state.busy.acquire()
    except TimeoutError as exc:
        raise HTTPException(503, detail="Сервис разбора занят, повторите позже.") from exc
    try:
        converted = await asyncio.to_thread(
            _convert, request.app.state.converter, data, fmt, max_pages
        )
    except Exception as exc:
        # The message of a parser error can quote the document; log its type only.
        log.warning(
            "conversion_failed format=%s bytes=%s error=%s", fmt, len(data), type(exc).__name__
        )
        raise HTTPException(422, detail="Документ не удалось разобрать.") from exc
    finally:
        request.app.state.busy.release()
    if not converted.markdown:
        raise HTTPException(422, detail="В документе не нашлось текста.")
    log.info(
        "converted format=%s bytes=%s pages=%s chars=%s seconds=%s",
        fmt,
        len(data),
        converted.pages,
        len(converted.markdown),
        converted.seconds,
    )
    return converted
