"""Builds the editable PPTX from what build.cjs measured in slides.html.

Every slide gets its background picture (the frosted panels, charts and bars, without text),
the pictures that can be moved on their own (device frames with screens, the cat, the Telegram
post) and native text boxes at the measured places, in Inter as on the site. Line breaks are
the ones the browser made, so a heading reads the same in PowerPoint.

    uv run --no-project --with python-pptx python build_pptx.py <workDir> <out.pptx>
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
ALIGN = {"center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT, "end": PP_ALIGN.RIGHT}
# PowerPoint measures a face a little differently: boxes get this much room to spare.
SLACK = 0.04


def px(value: float) -> Emu:
    return Emu(round(value * EMU_PER_PX))


def color(css: str) -> RGBColor | None:
    m = re.match(r"rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)", css)
    if not m or (m.group(4) is not None and float(m.group(4)) == 0):
        return None
    return RGBColor(*(int(m.group(i)) for i in (1, 2, 3)))


def font_of(style: dict) -> tuple[str, bool]:
    """The face PowerPoint knows by name, and whether it is the bold of that face."""
    weight = int(style["weight"])
    if style.get("mono"):
        return "Consolas", False
    if "inter display" in style["family"].lower():
        return ("Inter Display ExtraBold", False) if weight >= 800 else ("Inter Display", True)
    if weight >= 800:
        return "Inter ExtraBold", False
    if weight >= 700:
        return "Inter", True
    if weight >= 600:
        return "Inter SemiBold", False
    if weight >= 500:
        return "Inter Medium", False
    return "Inter", False


def style_run(run, style: dict) -> None:
    name, bold = font_of(style)
    run.font.name = name
    run.font.bold = bold
    run.font.italic = style.get("italic", False)
    run.font.size = Pt(round(style["size"] * PT_PER_PX * 2) / 2)
    rgb = color(style["color"])
    if rgb:
        run.font.color.rgb = rgb
    if style.get("ls") not in (None, "normal", "0px"):
        spacing = float(style["ls"].removesuffix("px")) * PT_PER_PX * 100
        run.font._element.set("spc", str(round(spacing)))
    rpr = run.font._element
    # A reference to a source is a superscript, as on the slide.
    if style.get("va") == "super":
        rpr.set("baseline", "30000")
        # PowerPoint draws a superscript about a third smaller than its size.
        run.font.size = Pt(round(style["size"] * PT_PER_PX * 1.5 * 2) / 2)
    for tag in ("a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rpr, qn(tag))
        el.set("typeface", name)


def pieces(runs: list[dict]) -> list[tuple[str, dict] | None]:
    """Runs cut at the browser's line breaks; None stands for a break. White space is collapsed
    as CSS does, and removed at the ends of every line."""
    out: list[tuple[str, dict] | None] = []
    for run in runs:
        if run.get("br"):
            out.append(None)
            continue
        text, style = run["text"], run["style"]
        cuts = [0, *run.get("breaks", []), len(text)]
        for k in range(len(cuts) - 1):
            if k:
                out.append(None)
            part = re.sub(r"[ \t\r\n\f]+", " ", text[cuts[k] : cuts[k + 1]])
            if style.get("transform") == "uppercase":
                part = part.upper()
            out.append((part, style))
    # Trim the spaces each line starts or ends with. A <br> and the new line the browser
    # reported right after it are one break.
    lines: list[list[tuple[str, dict]]] = [[]]
    for item in out:
        if item is None:
            if lines[-1]:
                lines.append([])
        elif item[0]:
            lines[-1].append(item)
    result: list[tuple[str, dict] | None] = []
    for n, line in enumerate(lines):
        if line:
            line[0] = (line[0][0].lstrip(), line[0][1])
            line[-1] = (line[-1][0].rstrip(), line[-1][1])
        if n:
            result.append(None)
        result.extend(item for item in line if item[0])
    while result and result[-1] is None:
        result.pop()
    return result


def add_text(slide, block: dict) -> None:
    r = dict(block["rect"])
    top, right, bottom, left = block["pad"]
    extra = max(8.0, r["w"] * SLACK)
    align = block["align"]
    if align == "center":
        r["x"] -= extra / 2
    elif align in ("right", "end"):
        r["x"] -= extra
    r["w"] += extra
    box = slide.shapes.add_textbox(px(r["x"]), px(r["y"]), px(r["w"]), px(r["h"]))
    frame = box.text_frame
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.margin_top, frame.margin_right = px(top), px(right)
    frame.margin_bottom, frame.margin_left = px(bottom), px(left)
    frame.vertical_anchor = MSO_ANCHOR.TOP
    # The breaks are given: PowerPoint must not add its own.
    frame.word_wrap = False
    paragraph = frame.paragraphs[0]
    paragraph.alignment = ALIGN.get(align, PP_ALIGN.LEFT)
    paragraph.line_spacing = Pt(block["lineHeight"] * PT_PER_PX)
    for item in pieces(block["runs"]):
        if item is None:
            paragraph.add_line_break()
            continue
        run = paragraph.add_run()
        run.text = item[0]
        style_run(run, item[1])
    text = "".join(run.text for run in paragraph.runs)
    box.name = f"Текст: {text[:40]}"


def add_picture(slide, base: Path, picture: dict) -> None:
    clip = picture["clip"]
    shape = slide.shapes.add_picture(
        str(base / picture["file"]), px(clip["x"]), px(clip["y"]), px(clip["w"]), px(clip["h"])
    )
    names = {"device": "Экран", "cat": "Кот", "image": "Картинка"}
    shape.name = f"{names.get(picture['kind'], 'Картинка')}: {picture['alt']}"[:80]
    if picture["alt"]:
        shape._element.nvPicPr.cNvPr.set("descr", picture["alt"])


def build(work: Path, out: Path) -> None:
    deck = json.loads((work / "deck.json").read_text(encoding="utf-8"))
    prs = Presentation()
    prs.slide_width, prs.slide_height = px(SLIDE_W), px(SLIDE_H)
    layout = prs.slide_layouts[6]  # blank
    for data in deck:
        slide = prs.slides.add_slide(layout)
        bg = slide.shapes.add_picture(str(work / data["bg"]), 0, 0, px(SLIDE_W), px(SLIDE_H))
        bg.name = "Фон слайда"
        for picture in data["pictures"]:
            add_picture(slide, work, picture)
        for block in data["texts"]:
            add_text(slide, block)
    prs.save(out)
    print(f"{len(deck)} slides -> {out}")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
