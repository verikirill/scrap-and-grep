# /// script
# requires-python = ">=3.12"
# dependencies = ["openpyxl"]
# ///
"""The organizers' dataset examples as JSON, for scripts/dataset_run.py.

    uv run scripts/dataset_json.py docs/task/dataset_v4.0.xlsx docs/task/dataset_v4.0.json
"""

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl

SOURCE, TARGET = (Path(arg) for arg in sys.argv[1:3])
_URL_RE = re.compile(r"https?://\S+")


def _date(value: object) -> str | None:
    if isinstance(value, datetime | date):
        return value.strftime("%Y-%m-%d")
    found = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", str(value or ""))
    return f"{found.group(3)}-{found.group(2)}-{found.group(1)}" if found else None


def main() -> None:
    book = openpyxl.load_workbook(SOURCE)
    specialists, management = book.worksheets[1], book.worksheets[3]
    examples: list[dict[str, Any]] = []
    for row in specialists.iter_rows(min_row=2, values_only=True):
        number, grouping, priority, name, when, source, wanted = row[:7]
        if not source:
            continue
        examples.append(
            {
                "id": f"specialist-{number}",
                "audience": "specialist",
                "grouping": str(grouping),
                "priority": str(priority),
                "title": str(name or ""),
                "date": _date(when),
                "urls": _URL_RE.findall(str(source)),
                "wanted": str(wanted or "").strip(),
            }
        )
    for row in management.iter_rows(min_row=2, values_only=True):
        number, tags, when, source, _form, wanted = row[:6]
        if not source:
            continue
        examples.append(
            {
                "id": f"management-{number}",
                "audience": "management",
                "grouping": str(tags),
                "priority": "",
                "title": "",
                "date": _date(when),
                "urls": _URL_RE.findall(str(source)),
                "wanted": str(wanted or "").strip(),
            }
        )
    TARGET.write_text(json.dumps(examples, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"{len(examples)} examples")


if __name__ == "__main__":
    main()
