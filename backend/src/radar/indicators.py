"""Indicators of compromise in an article and a CVSS vector in words.

Both are read from the text, not from the model: a reader of a specialist's
digest blocks an address or a hash on the strength of this line, so it must
be what the article printed.
"""

import ipaddress
import re

# Defanged forms come first in an article on an attack: "hxxps://", "evil[.]com".
_DOT = r"(?:\.|\[\.\]|\(\.\))"
_IPV4_RE = re.compile(rf"\b(?:\d{{1,3}}{_DOT}){{3}}\d{{1,3}}\b")
_HASH_RE = re.compile(r"\b(?:[a-f0-9]{64}|[a-f0-9]{40}|[a-f0-9]{32})\b", re.IGNORECASE)
# Only a defanged address is an indicator; an ordinary link is a reference.
_DEFANGED_URL_RE = re.compile(r"\b(?:hxxps?|https?)(?::|\[:\])//[^\s<>\"'`]+", re.IGNORECASE)
_DEFANGED_DOMAIN_RE = re.compile(r"\b[a-z0-9][a-z0-9-]*(?:\[\.\][a-z0-9-]+)+\b", re.IGNORECASE)
# "Обновите до 20.9.10.1" names a version, not a host.
_VERSION_BEFORE_RE = re.compile(r"(?:верси\w*|version|\bv|\bдо)\s*$", re.IGNORECASE)
MAX_INDICATORS = 20


def refang(value: str) -> str:
    """The indicator as a machine would read it, for comparing two spellings."""
    value = re.sub(r"\[\.\]|\(\.\)", ".", value)
    value = value.replace("[:]", ":")
    return re.sub(r"^hxxp", "http", value, flags=re.IGNORECASE).casefold().rstrip(".,;)")


def _defanged_ip(address: str) -> str:
    head, _, last = address.rpartition(".")
    return f"{head}[.]{last}"


def _defanged_url(url: str) -> str:
    url = re.sub(r"^http", "hxxp", url, flags=re.IGNORECASE)
    scheme, sep, rest = url.partition("//")
    host, slash, path = rest.partition("/")
    host = re.sub(r"(?<!\[)\.(?!\])", "[.]", host)
    return f"{scheme}{sep}{host}{slash}{path}"


def _public(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_global
    except ValueError:
        return False


def extract_indicators(text: str) -> list[str]:
    """Public IPv4 addresses, defanged addresses and domains, hashes, each
    defanged once, without repeats, in the order the text gives them."""
    found: list[tuple[int, str, str]] = []
    # What an address or a link took is no domain of its own: "4[.]7" of an IP.
    taken: list[tuple[int, int]] = []
    for match in _IPV4_RE.finditer(text):
        taken.append((match.start(), match.end()))
        address = refang(match.group(0))
        # "версии 5.4.2.1" has the shape of an address and is a version.
        if _VERSION_BEFORE_RE.search(text[max(0, match.start() - 16) : match.start()]):
            continue
        if _public(address):
            found.append((match.start(), address, _defanged_ip(address)))
    for match in _HASH_RE.finditer(text):
        value = match.group(0).lower()
        # A hash mixes digits and letters; a long decimal number is no hash.
        if value.isdigit() or value.isalpha():
            continue
        found.append((match.start(), value, value))
    for match in _DEFANGED_URL_RE.finditer(text):
        raw = match.group(0).rstrip(".,;)")
        if raw.lower().startswith("http") and "[.]" not in raw and "[:]" not in raw:
            continue
        taken.append((match.start(), match.end()))
        found.append((match.start(), refang(raw), _defanged_url(refang(raw))))
    for match in _DEFANGED_DOMAIN_RE.finditer(text):
        if any(start <= match.start() < end for start, end in taken):
            continue
        domain = refang(match.group(0))
        # A domain ends in a name, not in a number.
        if not re.search(r"[a-z]", domain.rsplit(".", 1)[-1]):
            continue
        found.append((match.start(), domain, domain.replace(".", "[.]")))
    seen: dict[str, str] = {}
    for _, key, shown in sorted(found):
        seen.setdefault(key, shown)
    return list(seen.values())[:MAX_INDICATORS]


# --- CVSS ------------------------------------------------------------------------

_ACCESS = {"N": "по сети", "A": "из смежной сети", "L": "локально", "P": "физический доступ"}
_COMPLEXITY = {"L": "низкая", "M": "средняя", "H": "высокая"}
_PRIVILEGES = {"N": "не нужны", "L": "низкие", "H": "высокие"}
# CVSS 3 has R (required); CVSS 4 has P (passive) and A (active).
_INTERACTION = {"N": "не нужны", "R": "нужны", "P": "нужны", "A": "нужны"}


# "CVSS 3.1", "CVSS v3.1", "CVSS:3.1/", "CVSS версии 3.1".
_CVSS_VERSION_RE = re.compile(r"CVSS[\s:]*(?:v|версии\s*)?([34]\.[01])\b", re.IGNORECASE)
# Metrics only CVSS 4 has.
_CVSS4_METRICS = {"AT", "VC", "VI", "VA"}


def _metrics(vector: str) -> list[str]:
    return [
        part
        for part in re.sub(r"\s", "", vector).split("/")
        if ":" in part and not part.upper().startswith("CVSS")
    ]


def cvss_version(text: str) -> str:
    """The one CVSS 3 or 4 version a text names; nothing when it names none or several."""
    versions = set(_CVSS_VERSION_RE.findall(text))
    return versions.pop() if len(versions) == 1 else ""


def normal_cvss_vector(vector: str, context: str = "") -> str:
    """The vector in one form: "CVSS:3.1/AV:N/..." when its version is known
    from the vector itself or from `context` (the score, the article), bare
    metrics when it is not; a CVSS 2 vector has no prefix. A string with no
    access metric is no vector."""
    metrics = _metrics(vector)
    keys = {part.split(":", 1)[0].upper() for part in metrics}
    if "AV" not in keys:
        return ""
    body = "/".join(metrics)
    if "AU" in keys:
        return body
    own = re.match(r"\s*CVSS:\s*(\d\.\d)", vector, re.IGNORECASE)
    if own:
        version = own.group(1)
    elif keys & _CVSS4_METRICS:
        version = "4.0"
    else:
        version = cvss_version(context)
        if version.startswith("4"):
            version = ""
    return f"CVSS:{version}/{body}" if version else body


def parse_cvss_vector(vector: str) -> list[tuple[str, str]]:
    """Network or local access, the complexity, the privileges and the user's
    part, in words; nothing for a string that is no vector. CVSS 2 has a
    medium complexity and neither privileges nor the user."""
    metrics = dict(part.split(":", 1) for part in _metrics(vector))
    if metrics.get("AV") not in _ACCESS:
        return []
    rows = [("Доступ", _ACCESS[metrics["AV"]])]
    if metrics.get("AC") in _COMPLEXITY:
        rows.append(("Сложность", _COMPLEXITY[metrics["AC"]]))
    if metrics.get("PR") in _PRIVILEGES:
        rows.append(("Права", _PRIVILEGES[metrics["PR"]]))
    if metrics.get("UI") in _INTERACTION:
        rows.append(("Действия пользователя", _INTERACTION[metrics["UI"]]))
    return rows
