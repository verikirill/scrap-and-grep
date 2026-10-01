"""The Data Bank of Information Security Threats of FSTEC of Russia (БДУ), bdu.fstec.ru.

Its feeds (ubi/vul/incident/rss, ubi/vul/danger/rss) give a one-sentence
teaser made from a template. A vulnerability's page draws its fields in the
browser from a JSON object written into the page, so the text a page reader
like trafilatura sees is template markup. The object is read here instead.
The values are taken as they come: a field of an unexpected type is left out,
not allowed to lose the rest.
"""

import json
import re
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from radar.logging import get_logger
from radar.text import strip_html

log = get_logger(__name__)

_HOSTS = frozenset({"bdu.fstec.ru", "www.bdu.fstec.ru"})
_PAGE_RE = re.compile(r"/vul/\d{4}-\d{5}/?")
_MODEL = "const v_model = reactive("
# Software versions listed at most; a library in every Linux distribution
# would fill the text with hundreds.
MAX_VERSIONS = 12
# The codes as the page's own templates spell them.
_EXPLOIT = {1: "существует", 2: "существует в открытом доступе"}
_STATE = {
    0: "потенциальная уязвимость",
    1: "подтверждена производителем",
    2: "подтверждена в ходе исследований",
}
_FIX = {1: "обновление программного обеспечения", 2: "организационные меры"}


def is_vulnerability_page(url: str) -> bool:
    parts = urlsplit(url)
    return (parts.hostname or "") in _HOSTS and bool(_PAGE_RE.fullmatch(parts.path))


def vulnerability(page: str) -> dict[str, Any] | None:
    """The fields of the vulnerability the page shows, as the page has them."""
    start = page.find(_MODEL)
    if start < 0:
        return None
    index = start + len(_MODEL)
    while index < len(page) and page[index].isspace():
        index += 1
    try:
        model, _ = json.JSONDecoder().raw_decode(page, index)
    except (ValueError, RecursionError) as exc:
        # The marker is there but the data is not: the page has changed.
        log.info("bdu_page_unreadable", error=type(exc).__name__)
        return None
    if not isinstance(model, dict) or not isinstance(model.get("vul_desc"), str):
        return None
    return model if model["vul_desc"].strip() else None


def page_text(page: str) -> str | None:
    """The vulnerability as plain text, field by field, for summaries and search."""
    model = vulnerability(page)
    if model is None:
        return None
    # BDU leaves the full stop off its descriptions.
    description = _plain(model["vul_desc"])
    lines = [description if description.endswith((".", "!", "?")) else f"{description}."]
    if software := _software(model):
        lines.append(f"Уязвимое ПО: {'; '.join(software)}.")
    if danger := _lines(model.get("vul_critu")):
        lines.append(f"Уровень опасности: {'; '.join(danger)}.")
    lines += [_plain(strip_html(vector)) for vector in _strings(model.get("cvsses3"))]
    for cwe in _dicts(model.get("cwes")):
        lines.append(
            f"Тип ошибки: CWE-{_plain(cwe.get('cwe_idn'))}, {_plain(cwe.get('cwe_name'))}."
        )
    if ids := [_plain(strip_html(value)) for value in _strings(model.get("idvals"))]:
        lines.append(f"Идентификаторы: {'; '.join(ids)}.")
    lines += _flags(model)
    if found := _date(model.get("vul_datv")):
        lines.append(f"Дата выявления: {found:%d.%m.%Y}.")
    if measures := _plain(model.get("vul_vmer")):
        lines.append(f"Меры по устранению: {measures}")
    return "\n".join(line for line in lines if line)


def _flags(model: dict[str, Any]) -> list[str]:
    lines = []
    if exploit := _EXPLOIT.get(_number(model.get("vul_expl"))):
        lines.append(f"Эксплойт: {exploit}.")
    if _number(model.get("vul_incident")):
        lines.append("Используется в атаках.")
    if state := _STATE.get(_number(model.get("vul_state"))):
        lines.append(f"Статус: {state}.")
    if fix := _FIX.get(_number(model.get("vul_elimination"))):
        lines.append(f"Способ устранения: {fix}.")
    return lines


def _software(model: dict[str, Any]) -> list[str]:
    named = []
    for version in _dicts(model.get("versions")):
        soft = _dict(version.get("soft"))
        vendor = _dict(soft.get("vendor"))
        parts = (vendor.get("vnd_name"), soft.get("sft_name"), version.get("ver_name"))
        named.append(_plain(" ".join(part for part in parts if isinstance(part, str))))
    software = list(dict.fromkeys(name for name in named if name))
    if not software:
        software = [_plain(name) for name in _strings(model.get("softs")) if name.strip()]
    if len(software) > MAX_VERSIONS:
        return [*software[:MAX_VERSIONS], f"и ещё {len(software) - MAX_VERSIONS}"]
    return software


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _lines(value: object) -> list[str]:
    text = value if isinstance(value, str) else ""
    return [_plain(line) for line in text.splitlines() if line.strip()]


def _plain(value: object) -> str:
    return " ".join(str(value).split()) if isinstance(value, (str, int)) else ""


def _number(value: object) -> int:
    """A code as the page has it: 1, "1", 1.0 or true."""
    try:
        if isinstance(value, (bool, int, float)):
            return int(value)
        if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
            return int(value)
    except ValueError, OverflowError:
        # NaN and Infinity pass for numbers in Python's JSON.
        pass
    return 0


def _date(value: object) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if isinstance(value, str) else None
    except ValueError:
        return None
