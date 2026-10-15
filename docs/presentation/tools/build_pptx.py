"""Builds the editable PPTX from what extract.cjs measured in slides.html.

Text goes into text boxes at the measured positions (Georgia for headings, Segoe UI for the rest),
tables become native tables, and charts, schemes, screenshots and card backgrounds are the 2x PNG
pictures extract.cjs cut from the rendered slides.

    uv run --no-project --with python-pptx --with pillow python build_pptx.py <extractDir> <out.pptx>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

SLIDE_W, SLIDE_H = 1920, 1080
EMU_PER_PX = 12192000 // SLIDE_W  # a 1920 px slide is 13.333 in wide
PT_PER_PX = 0.5  # 1920 px -> 960 pt
BACKGROUND = RGBColor(0xF4, 0xF2, 0xEC)
ALIGN = {"center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT, "end": PP_ALIGN.RIGHT}


def px(value: float) -> Emu:
    return Emu(round(value * EMU_PER_PX))


def color(css: str) -> RGBColor | None:
    m = re.match(r"rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)", css)
    if not m or (m.group(4) is not None and float(m.group(4)) == 0):
        return None
    return RGBColor(*(int(m.group(i)) for i in (1, 2, 3)))


def font_of(style: dict) -> tuple[str, bool]:
    """Font name and bold flag for a CSS style: Georgia for serif, Consolas for code, else Segoe UI."""
    weight = int(style["weight"])
    family = style["family"].lower()
    if style.get("code") or "consolas" in family or "mono" in family:
        return "Consolas", False
    if "georgia" in family or ("serif" in family and "sans" not in family):
        return "Georgia", weight >= 600
    if 560 <= weight < 700:
        return "Segoe UI Semibold", False
    return "Segoe UI", weight >= 700


def clean(text: str, style: dict) -> str:
    if style.get("ws") not in ("pre", "pre-wrap"):
        text = re.sub(r"[ \t\r\n\f]+", " ", text)
    if style.get("transform") == "uppercase":
        text = text.upper()
    return text


def style_run(run, style: dict) -> None:
    name, bold = font_of(style)
    run.font.name = name
    run.font.bold = bold
    run.font.italic = style.get("italic", False)
    run.font.size = Pt(style["size"] * PT_PER_PX)
    rgb = color(style["color"])
    if rgb:
        run.font.color.rgb = rgb
    if style.get("ls") not in (None, "normal"):
        spacing = float(style["ls"].removesuffix("px")) * PT_PER_PX * 100
        run.font._element.set("spc", str(round(spacing)))
    # Latin and Cyrillic both take the same face.
    rpr = run.font._element
    for tag in ("a:cs", "a:ea"):
        el = rpr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rpr, qn(tag))
        el.set("typeface", name)


def fill_paragraph(paragraph, runs: list[dict], lines: list[str] | None = None) -> None:
    """Writes runs into a paragraph; for headings the measured line breaks are kept."""
    items = runs
    if lines:
        style = next(r["style"] for r in runs if "style" in r)
        items = []
        for k, line in enumerate(lines):
            items.append({"text": line.strip() if k else line.rstrip(), "style": style})
            if k < len(lines) - 1:
                items.append({"br": True})
    first = True
    for item in items:
        if item.get("br"):
            paragraph.add_line_break()
            first = True
            continue
        text = clean(item["text"], item["style"])
        if first:
            text = text.lstrip()
        if not text:
            continue
        first = False
        run = paragraph.add_run()
        run.text = text
        style_run(run, item["style"])
    # A trailing space at the end of a block does not belong to the text.
    if paragraph.runs:
        last = paragraph.runs[-1]
        last.text = last.text.rstrip()


def set_frame(frame, pad: list[float], valign: str = "top") -> None:
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.NONE
    top, right, bottom, left = pad
    frame.margin_top, frame.margin_right = px(top), px(right)
    frame.margin_bottom, frame.margin_left = px(bottom), px(left)
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE if valign == "middle" else MSO_ANCHOR.TOP


def add_text(slide, block: dict) -> None:
    r = dict(block["rect"])
    if block["slideNumber"]:
        r["x"], r["w"] = r["x"] + r["w"] - 80, 80
        block = {**block, "align": "right"}
    box = slide.shapes.add_textbox(px(r["x"]), px(r["y"]), px(r["w"]) + px(2), px(r["h"]))
    frame = box.text_frame
    set_frame(frame, block["pad"])
    # One measured line stays one line even if PowerPoint measures the face a little wider.
    if r["h"] < block["lineHeight"] * 1.5:
        frame.word_wrap = False
    paragraph = frame.paragraphs[0]
    paragraph.alignment = ALIGN.get(block["align"], PP_ALIGN.LEFT)
    paragraph.line_spacing = Pt(block["lineHeight"] * PT_PER_PX)
    fill_paragraph(paragraph, block["runs"], block.get("lines"))
    box.name = f"{block['tag']} text"


def border(cell, side: str, width: float, rgb: RGBColor | None) -> None:
    tcpr = cell._tc.get_or_add_tcPr()
    tag = {"L": "a:lnL", "R": "a:lnR", "T": "a:lnT", "B": "a:lnB"}[side]
    for old in tcpr.findall(qn(tag)):
        tcpr.remove(old)
    line = etree.SubElement(tcpr, qn(tag), w=str(round(width * EMU_PER_PX)) if rgb else "0")
    if rgb:
        fill = etree.SubElement(line, qn("a:solidFill"))
        etree.SubElement(fill, qn("a:srgbClr"), val=str(rgb))
    else:
        etree.SubElement(line, qn("a:noFill"))
    # Borders must come before the cell fill in tcPr.
    for tag in ("a:noFill", "a:solidFill"):
        fill_el = tcpr.find(qn(tag))
        if fill_el is not None:
            tcpr.remove(fill_el)
            tcpr.append(fill_el)


def add_table(slide, table: dict) -> None:
    rows = table["rows"]
    widest = max(rows, key=lambda row: len(row["cells"]))
    lefts = [c["rect"]["x"] for c in widest["cells"]] + [table["rect"]["x"] + table["rect"]["w"]]
    widths = [lefts[i + 1] - lefts[i] for i in range(len(widest["cells"]))]
    r = table["rect"]
    shape = slide.shapes.add_table(len(rows), len(widths), px(r["x"]), px(r["y"]), px(r["w"]), px(r["h"]))
    tbl = shape.table
    tbl.first_row = False
    tbl.horz_banding = False
    for i, w in enumerate(widths):
        tbl.columns[i].width = px(w)
    for i, row in enumerate(rows):
        tbl.rows[i].height = px(row["rect"]["h"])
        col = 0
        for cell_data in row["cells"]:
            cell = tbl.cell(i, col)
            span = cell_data["colspan"]
            if span > 1:
                cell.merge(tbl.cell(i, col + span - 1))
            cell.fill.background()
            set_frame(cell.text_frame, cell_data["pad"])
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.alignment = ALIGN.get(cell_data["align"], PP_ALIGN.LEFT)
            paragraph.line_spacing = Pt(cell_data["lineHeight"] * PT_PER_PX)
            fill_paragraph(paragraph, cell_data["runs"])
            for k in range(span):
                target = tbl.cell(i, col + k)
                for side in "LRT":
                    border(target, side, 0, None)
                b = cell_data["borderBottom"]
                border(target, "B", b["w"], color(b["color"]) if b["style"] != "none" and b["w"] else None)
            col += span
    shape.name = "table"


def add_picture(slide, base: Path, picture: dict) -> None:
    clip = picture["clip"]
    shape = slide.shapes.add_picture(
        str(base / picture["file"]), px(clip["x"]), px(clip["y"]), px(clip["w"]), px(clip["h"])
    )
    shape.name = f"{picture['kind']} {picture['id'] or picture['label'] or picture['alt']}".strip()
    if picture["alt"]:
        shape._element.nvPicPr.cNvPr.set("descr", picture["alt"])


def build(extract_dir: Path, out: Path) -> None:
    deck = json.loads((extract_dir / "deck.json").read_text(encoding="utf-8"))
    prs = Presentation()
    prs.slide_width, prs.slide_height = px(SLIDE_W), px(SLIDE_H)
    layout = prs.slide_layouts[6]  # blank
    for data in deck:
        slide = prs.slides.add_slide(layout)
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = BACKGROUND
        for picture in data["pictures"]:
            add_picture(slide, extract_dir, picture)
        for table in data["tables"]:
            add_table(slide, table)
        for block in data["texts"]:
            add_text(slide, block)
    prs.save(out)
    print(f"{len(deck)} slides -> {out}")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
