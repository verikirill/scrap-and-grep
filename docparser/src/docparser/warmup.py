"""Download every model the service uses, at image build time.

    python -m docparser.warmup

The running container has no route to the internet, so nothing may be left to
fetch on first use. Converting a generated picture exercises the whole chain:
layout, table structure and OCR.
"""

import logging
from io import BytesIO

from docling.datamodel.base_models import ConversionStatus, DocumentStream
from PIL import Image, ImageDraw

from docparser.app import build_converter


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    image = Image.new("L", (900, 300), color=255)
    ImageDraw.Draw(image).text((40, 120), "Resume 2026: SCADA, SIEM, Linux", fill=0, font_size=36)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    result = build_converter().convert(DocumentStream(name="warmup.png", stream=buffer))
    if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
        raise SystemExit(f"warm-up conversion ended with {result.status.name}")
    logging.getLogger("docparser").info(
        "models ready, warm-up text: %r", result.document.export_to_markdown()[:80]
    )


if __name__ == "__main__":
    main()
