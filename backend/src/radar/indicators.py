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
_VERSION_BEFORE_RE = re.compile(r"(?:верси\w*|version|\bv)\s*$", re.IGNORECASE)
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
_PRIVILEGES = {"N": "не нужны", "L": "низкие", "H": "высокие"}
# CVSS 3 has R (required); CVSS 4 has P (passive) and A (active).
_INTERACTION = {"N": "не нужны", "R": "нужны", "P": "нужны", "A": "нужны"}


def parse_cvss_vector(vector: str) -> list[tuple[str, str]]:
    """Network or local access, the privileges and the user's part, in words;
    nothing for a string that is no vector."""
    metrics = dict(
        part.split(":", 1)
        for part in re.sub(r"\s", "", vector).split("/")
        if ":" in part and not part.upper().startswith("CVSS")
    )
    if metrics.get("AV") not in _ACCESS:
        return []
    rows = [("Доступ", _ACCESS[metrics["AV"]])]
    if metrics.get("PR") in _PRIVILEGES:
        rows.append(("Права", _PRIVILEGES[metrics["PR"]]))
    if metrics.get("UI") in _INTERACTION:
        rows.append(("Действия пользователя", _INTERACTION[metrics["UI"]]))
    return rows
