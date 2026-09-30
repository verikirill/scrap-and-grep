"""Recognise an uploaded file by its content, not by its name."""

import io
import zipfile

from radar.resume.model import ResumeError

# Formats the built-in parser reads without any model.
BUILTIN_FORMATS = ("pdf", "docx", "txt", "md")
# Formats that need the docling service: layout analysis, OCR, slides, HTML.
DOCLING_FORMATS = (*BUILTIN_FORMATS, "pptx", "odt", "html", "png", "jpg")

_ZIP_MAX_ENTRIES = 3000
# A resume with pictures unpacks to a few megabytes; far more is a bomb.
_ZIP_MAX_UNPACKED = 30_000_000
_TEXT_EXTENSIONS = {"md": "md", "markdown": "md", "html": "html", "htm": "html"}


def _office_format(data: bytes) -> str:
    """Tell DOCX, PPTX and ODT apart, and refuse an archive that unpacks to far
    more than any document would (a decompression bomb)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > _ZIP_MAX_ENTRIES:
                raise ResumeError("Файл выглядит повреждённым: в нём слишком много частей.")
            if sum(entry.file_size for entry in entries) > _ZIP_MAX_UNPACKED:
                raise ResumeError("Файл слишком велик в распакованном виде.")
            names = {entry.filename for entry in entries}
            if "word/document.xml" in names:
                return "docx"
            if "ppt/presentation.xml" in names:
                return "pptx"
            if "mimetype" in names:
                with archive.open("mimetype") as mimetype:
                    # Read the head only: the entry itself may be the bomb.
                    if b"opendocument.text" in mimetype.read(200):
                        return "odt"
    except zipfile.BadZipFile as exc:
        raise ResumeError("Файл повреждён и не открывается.") from exc
    raise ResumeError("Это архив, а не документ. Загрузите PDF, DOCX или текст.")


def decode_text(data: bytes) -> str | None:
    """Decode a plain-text upload. Russian resumes saved by old editors come in
    Windows-1251, so that is tried after UTF-8."""
    if b"\x00" in data[:4096]:
        return None
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def detect_format(data: bytes, filename: str) -> str:
    """Return the format of the upload or raise `ResumeError`.

    The file name is only a hint for text formats; a binary format is decided
    by its signature, so a renamed executable does not reach a parser.
    """
    if not data:
        raise ResumeError("Файл пуст.")
    head = data[:8]
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        return _office_format(data)
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        raise ResumeError("Старый формат .doc не поддерживается. Сохраните файл как DOCX или PDF.")
    text = decode_text(data)
    if text is None:
        raise ResumeError("Формат файла не распознан. Подойдут PDF, DOCX, TXT или Markdown.")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if text.lstrip()[:200].lower().startswith(("<!doctype html", "<html")):
        return "html"
    return _TEXT_EXTENSIONS.get(extension, "txt")
