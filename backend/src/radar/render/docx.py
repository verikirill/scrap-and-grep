"""Render a digest as a DOCX document."""

from io import BytesIO

from docx import Document
from docx.enum.text import WD_BREAK
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docx.text.paragraph import Paragraph

from radar.cards import TAG_LABELS, defang
from radar.render.markdown import (
    CHANGES_TITLE,
    PLAN_TITLE,
    card_rows,
    change_line,
    format_date,
    format_datetime,
    item_meta,
    manual_sentence,
    methodology,
)
from radar.views import DigestView, ItemView

_LINK_COLOR = "1F5FBF"
_MUTED = RGBColor(0x5F, 0x6B, 0x7A)


def add_hyperlink(paragraph: Paragraph, url: str, text: str, *, bold: bool = False) -> None:
    """python-docx has no hyperlink API; build the run by hand."""
    relation = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relation)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), _LINK_COLOR)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    properties.append(color)
    properties.append(underline)
    if bold:
        properties.append(OxmlElement("w:b"))
    run.append(properties)
    text_node = OxmlElement("w:t")
    text_node.text = text
    text_node.set(qn("xml:space"), "preserve")
    run.append(text_node)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _muted(paragraph: Paragraph, text: str) -> None:
    run = paragraph.add_run(text)
    run.font.size = Pt(9)
    run.font.color.rgb = _MUTED


def _item(document: Document, item: ItemView) -> None:  # type: ignore[valid-type]
    heading = document.add_paragraph()  # type: ignore[attr-defined]
    heading.paragraph_format.space_before = Pt(10)
    heading.paragraph_format.keep_with_next = True
    add_hyperlink(heading, item.url, item.headline, bold=True)

    _muted(document.add_paragraph(), " · ".join(item_meta(item)))  # type: ignore[attr-defined]

    if item.headline != item.title:
        _muted(document.add_paragraph(), f"Оригинал: {item.title}")  # type: ignore[attr-defined]
    if item.summary:
        document.add_paragraph(item.summary)  # type: ignore[attr-defined]
    for label, value in card_rows(item):
        row = document.add_paragraph(style="List Bullet")  # type: ignore[attr-defined]
        row.add_run(f"{label}: ").bold = True
        row.add_run(value)
    if item.tags:
        tags = document.add_paragraph()  # type: ignore[attr-defined]
        tags.add_run("Признаки: ").bold = True
        tags.add_run(" · ".join(TAG_LABELS[tag] for tag in item.tags))
    if item.why:
        why = document.add_paragraph()  # type: ignore[attr-defined]
        why.add_run("Почему важно: ").bold = True
        why.add_run(item.why)
    if item.links:
        _muted(
            document.add_paragraph(),  # type: ignore[attr-defined]
            "Ссылки из поста: " + ", ".join(defang(url) for url in item.links),
        )
    if item.unsupported:
        _muted(
            document.add_paragraph(),  # type: ignore[attr-defined]
            f"Нет в тексте статьи, убрано проверкой: {', '.join(item.unsupported)}.",
        )
    if item.duplicates:
        also = document.add_paragraph()  # type: ignore[attr-defined]
        also.add_run("Также об этом: ")
        for index, duplicate in enumerate(item.duplicates):
            if index:
                also.add_run(", ")
            add_hyperlink(also, duplicate.url, duplicate.source_name)


def _extras(document: Document, digest: DigestView) -> None:  # type: ignore[valid-type]
    """The plan for the shift, what changed and the period in numbers, as in Markdown."""
    if digest.plan:
        document.add_heading(PLAN_TITLE, level=1)  # type: ignore[attr-defined]
        for entry in digest.plan:
            paragraph = document.add_paragraph("☐ ")  # type: ignore[attr-defined]
            add_hyperlink(paragraph, entry.url, entry.headline, bold=True)
            for step in entry.steps:
                document.add_paragraph(step, style="List Bullet")  # type: ignore[attr-defined]
            if entry.facts:
                _muted(document.add_paragraph(), "; ".join(entry.facts))  # type: ignore[attr-defined]
    if digest.changes:
        document.add_heading(CHANGES_TITLE, level=1)  # type: ignore[attr-defined]
        for change in digest.changes:
            paragraph = document.add_paragraph(style="List Bullet")  # type: ignore[attr-defined]
            paragraph.add_run(f"{change.id}, ").bold = True
            add_hyperlink(paragraph, change.url, change.headline)
            paragraph.add_run(f": {change_line(change)}")
    if digest.numbers:
        document.add_heading(digest.numbers_title, level=1)  # type: ignore[attr-defined]
        before = any(row.before is not None for row in digest.numbers)
        header = ["Признак", "Записей", *(["В прошлом выпуске"] if before else [])]
        table = document.add_table(rows=1, cols=len(header))  # type: ignore[attr-defined]
        table.style = "Table Grid"
        for cell, text in zip(table.rows[0].cells, header, strict=True):
            cell.text = text
        for row in digest.numbers:
            values = [row.label, str(row.count), *([str(row.before)] if before else [])]
            for cell, text in zip(table.add_row().cells, values, strict=True):
                cell.text = text


def render_docx(digest: DigestView) -> bytes:
    document = Document()
    style = document.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    document.add_heading(digest.title or f"Дайджест для профиля «{digest.profile_name}»", level=0)
    _muted(
        document.add_paragraph(),
        f"Профиль: {digest.profile_name} (версия {digest.profile_version}) · "
        f"Период: {format_date(digest.period_start)} - {format_date(digest.period_end)} · "
        f"Сформирован: {format_datetime(digest.finished_at or digest.created_at)} МСК",
    )
    if digest.manual:
        document.add_paragraph().add_run(manual_sentence(digest)).italic = True

    if digest.profile.audience == "management" and digest.implications:
        document.add_heading("Что это значит для нас", level=1)
        for point in digest.implications:
            document.add_paragraph(point, style="List Bullet")
    if digest.highlights:
        document.add_heading("Главное", level=1)
        for highlight in digest.highlights:
            document.add_paragraph(highlight, style="List Bullet")
    _extras(document, digest)
    if not digest.topics:
        document.add_paragraph("За выбранный период публикаций по интересам профиля не найдено.")

    for number, topic in enumerate(digest.topics, start=1):
        document.add_heading(f"{number}. {topic.title}", level=1)
        if topic.overview:
            document.add_paragraph(topic.overview)
        for item in topic.items:
            _item(document, item)

    document.add_paragraph().add_run().add_break(WD_BREAK.LINE)
    document.add_heading("Как составлен выпуск", level=2)
    for line in methodology(digest):
        document.add_paragraph(line, style="List Bullet")

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
