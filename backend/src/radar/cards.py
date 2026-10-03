"""Record kinds, priorities and the check of an entry against its article.

The organizers' dataset groups a specialist's digest by what a publication
reports: an attack, a vulnerability, or other news. Within a group it ranks
by fixed rules: an attack on the Russian energy sector above one on another
Russian sector, and both above one abroad; a vulnerability with an exploit
above one without. Management gets a short brief marked with the dataset's
twelve tags instead.

The model fills the cards; everything here is deterministic. A card field
the article's text does not support is taken out, so a reader never acts on
a CVSS score or a version number the model made up.
"""

import re
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from radar.domain import (
    AttackCard,
    AttackTechnique,
    Exploit,
    ItemSummary,
    ManagementTag,
    Priority,
    RecordKind,
    VulnerabilityCard,
    VulnerabilityReference,
)
from radar.indicators import extract_indicators, parse_cvss_vector, refang
from radar.text import numbers, split_sentences

__all__ = ["extract_indicators", "parse_cvss_vector"]

KIND_LABELS: dict[RecordKind, str] = {
    "attack": "Атака",
    "vulnerability": "Уязвимость",
    "news": "Новость",
}
# Sections of a specialist's digest, in this order; other news follows by topic.
SECTION_TITLES: dict[RecordKind, str] = {"attack": "Атаки", "vulnerability": "Уязвимости"}
# The same, keyed by the plain strings a graph state carries.
SECTION_KINDS: dict[str | None, RecordKind] = {"attack": "attack", "vulnerability": "vulnerability"}
PRIORITY_LABELS: dict[Priority, str] = {"high": "высокий", "medium": "средний", "low": "низкий"}
PRIORITY_ORDER: dict[Priority | None, int] = {"high": 0, "medium": 1, "low": 2, None: 3}
EXPLOIT_LABELS: dict[Exploit, str] = {
    "in_the_wild": "используется в атаках",
    "public": "есть публичный эксплойт",
    "none": "нет",
    "unknown": "нет данных",
}
TAG_LABELS: dict[ManagementTag, str] = {
    "ru": "В РФ",
    "abroad": "Вне РФ",
    "financial_loss": "Крупные финансовые потери",
    "critical_infrastructure": "Нарушение работы критической инфраструктуры",
    "energy": "Энергетика",
    "industry": "Промышленность",
    "reputation": "Имиджевые потери",
    "data_leak": "Утечка чувствительной информации",
    "government_law": "Госсектор и правовое поле",
    "mass_service": "Уязвимый массовый сервис",
    "people_events": "Кадры, мероприятия и конференции",
    "curious": "Может быть интересно",
}
NO_DATA = "нет данных"


def priority(kind: RecordKind, text: ItemSummary | None) -> Priority | None:
    """The dataset's priority of a specialist's attack or vulnerability card.
    News has none, and neither has a management brief: it carries no card."""
    attack = text.attack if text else None
    vulnerability = text.vulnerability if text else None
    if kind == "attack" and attack is not None:
        if not attack.victim_in_russia:
            return "low"
        return "high" if attack.energy_sector else "medium"
    if kind == "vulnerability" and vulnerability is not None:
        return "high" if vulnerability.exploit in ("in_the_wild", "public") else "medium"
    return None


def priority_reason(kind: RecordKind, text: ItemSummary | None) -> str:
    """Why the rule gave this priority, in the dataset's words."""
    level = priority(kind, text)
    if kind == "attack":
        return {"high": "РФ, энергетика или промышленность", "medium": "РФ, другие отрасли"}.get(
            level or "", "вне РФ или страна не названа"
        )
    if kind == "vulnerability":
        exploit = text.vulnerability.exploit if text and text.vulnerability else "unknown"
        return "эксплойт: " + EXPLOIT_LABELS[exploit]
    return ""


# --- What a publication reports ---------------------------------------------

_ID_RE = re.compile(
    r"\b(?:CVE-\d{4}-\d{4,7}|(?:BDU|БДУ):\s?\d{4}-\d{5}|GHSA(?:-[0-9a-z]{4}){3}|PT-\d{4}-\d{3,6})\b",
    re.IGNORECASE,
)
_VULNERABILITY_RE = re.compile(
    r"уязвимост|vulnerab|zero[- ]day|0-day|\bRCE\b|патч|исправлени|security update|"
    r"\bpatch|advisory|бюллетен",
    re.IGNORECASE,
)
_ATTACK_RE = re.compile(
    r"атак[аиуеоы]\b|атаковал|кибератак|группировк|\bAPT\s?\d*|шифровальщик|вымогател|"
    r"ransomware|бэкдор|backdoor|фишинг|phishing|кампани[яиюей]|threat actor|взлом|hacked|"
    r"breach|вредонос|malware|троян|trojan|стилер|stealer",
    re.IGNORECASE,
)


def identifiers(text: str) -> list[str]:
    """CVE, BDU, GHSA and PT ids in the text, written one way: "BDU:2025-10116"."""
    found = []
    for match in _ID_RE.findall(text.replace("\u2011", "-").replace("\u2010", "-")):
        value = re.sub(r"\s", "", match).upper().replace("БДУ:", "BDU:")
        found.append(value)
    return list(dict.fromkeys(found))


def guess_kind(title: str, body: str) -> RecordKind:
    """What a publication reports, by its words: the offline stand-in for the model."""
    if _VULNERABILITY_RE.search(title) or _ID_RE.search(title):
        return "vulnerability"
    if _ATTACK_RE.search(title):
        return "attack"
    attack_words = len(_ATTACK_RE.findall(body))
    vulnerability_words = len(_VULNERABILITY_RE.findall(body)) + 2 * len(identifiers(body))
    if vulnerability_words >= 3 and vulnerability_words > attack_words:
        return "vulnerability"
    if attack_words >= 3:
        return "attack"
    return "news"


# --- Evidence in the text ----------------------------------------------------

# Phrasings from real articles: "Mandiant сообщает об эксплуатации 0-day",
# "в сети используются две 0-day", "Cisco Patches Exploited ... Zero-Day".
_IN_THE_WILD_RE = re.compile(
    r"(?:использу|эксплуатиру)\w* (?:\w+ ){0,3}?(?:в атаках|в сети|в реальных|злоумышленник|"
    r"хакер|группировк|в дикой)|активно эксплуатир|уже эксплуатир|под активной эксплуатацией|"
    r"в (?:сети|атаках|реальных атаках) (?:\w+ ){0,2}?(?:использу|эксплуатиру)\w*|"
    r"(?:сообщ|зафиксир|обнаруж|подтверд)\w* (?:\w+ ){0,2}?(?:эксплуатаци|атак)\w* (?:на |с )?"
    r"(?:0-day|уязвимост|нулев)|об эксплуатации (?:0-day|уязвимост|нулев)|"
    r"злоумышленник\w* (?:активно |уже )?(?:использу|эксплуатиру)\w* (?:\w+ ){0,2}?уязвимост|"
    r"exploit\w*[^.]{0,40}?in the wild|in the wild[^.]{0,40}?exploit|actively exploited|"
    r"under active exploitation|known exploited|"
    r"\bexploited (?:[\w-]+ ){0,4}?(?:zero-day|0-day|vulnerabilit|flaw|bug)|"
    r"(?:zero-day|0-day|vulnerabilit\w*|flaws?|bugs?) (?:\w+ ){0,3}?(?:being |been )?exploited|"
    r"attackers (?:are |have been )?exploiting|exploitation (?:attempts|activity)|\bKEV\b",
    re.IGNORECASE,
)
# Said to be absent. Taken out of the text before the signs above are looked
# for: "not aware of any exploitation in the wild" must not read as "in the wild".
_NO_EXPLOIT_RE = re.compile(
    r"эксплойт\w*:? (?:отсутству|нет\b|не (?:обнаруж|выявлен|известн|опубликован))|"
    r"нет (?:публичн\w+ )?эксплойт|не эксплуатировал\w*|"
    r"не (?:использу|эксплуатиру)\w* (?:\w+ ){0,2}?(?:в атаках|в сети|злоумышленник|хакер)|"
    r"(?:признак\w*|случа\w*|сведени\w*) (?:\w+ ){0,2}?(?:эксплуатации|использования)[^.]{0,60}?"
    r"не (?:обнаруж|выявл|зафиксир|поступал)\w*|"
    r"не (?:обнаружен|выявлен|зафиксирован)\w* (?:\w+ ){0,2}?(?:эксплуатаци|использовани)\w*|"
    r"not aware of (?:any )?(?:active |public |malicious )?(?:exploitation|exploits?|use)"
    r"(?: [^.]{0,40})?|no evidence (?:of|that)[^.]{0,80}|no (?:public |known )?exploits?\b|"
    r"not (?:been |yet )?(?:\w+ )?exploited(?: in the wild)?",
    re.IGNORECASE,
)
_PUBLIC_EXPLOIT_RE = re.compile(
    r"эксплойт\w*:? (?:существует|опубликован|доступ|в открытом)|публичн\w* эксплойт|"
    r"опубликова\w* (?:PoC|эксплойт)|proof[- ]of[- ]concept|\bPoC\b|"
    r"public(?:ly available)? exploit|"
    r"exploit (?:code )?(?:is |was |has been )?(?:publicly )?(?:available|released|published)",
    re.IGNORECASE,
)
_CWE_RE = re.compile(r"\bCWE-\d{1,5}\b", re.IGNORECASE)
_IOC_RE = re.compile(
    r"\bIoCs?\b|индикатор\w* компрометации|indicators? of compromise|\bSHA-?(?:1|256)\b|\bMD5\b|"
    r"\b[0-9a-f]{32,64}\b",
    re.IGNORECASE,
)


def exploit_evidence(text: str) -> Exploit:
    """What the text says about an exploit; "unknown" when it says nothing."""
    affirmed = _NO_EXPLOIT_RE.sub(" ", text)
    if _IN_THE_WILD_RE.search(affirmed):
        return "in_the_wild"
    if _PUBLIC_EXPLOIT_RE.search(affirmed):
        return "public"
    if affirmed != text:
        return "none"
    return "unknown"


def _compact(text: str) -> str:
    return re.sub(r"\s", "", text).upper().removeprefix("CVSS:3.1/").removeprefix("CVSS:3.0/")


def _mentioned(name: str, source: str) -> bool:
    """A name the model took from the text: the whole of it, or its first long word."""
    name = name.strip().casefold()
    if not name:
        return False
    haystack = source.casefold()
    if name in haystack:
        return True
    words = [word for word in re.split(r"[\s,()«»\"']+", name) if len(word) >= 4]
    return bool(words) and words[0] in haystack


def _figures_supported(value: str, allowed: set[str]) -> bool:
    return numbers(value) <= allowed


def check_vulnerability(
    card: VulnerabilityCard, source: str
) -> tuple[VulnerabilityCard, list[str]]:
    """The card with what the text does not support taken out, and the labels
    of what was taken out."""
    removed: list[str] = []
    allowed = numbers(source)
    known = identifiers(source)
    ids = [value for value in identifiers(" ".join(card.ids)) if value in known]
    if len(ids) < len(card.ids):
        removed.append("Идентификаторы")
    if not ids and len(known) <= 3:
        # The model left them out; the publication names them.
        ids = known
    updates: dict[str, object] = {"ids": tuple(ids)}
    score = numbers(card.cvss_score)
    if card.cvss_score and not (score and score <= allowed):
        updates["cvss_score"] = ""
        removed.append("Оценка CVSS")
    if card.cvss_vector and _compact(card.cvss_vector) not in _compact(source):
        updates["cvss_vector"] = ""
        removed.append("Вектор CVSS")
    for field, label in (
        ("name", "Название"),
        ("affected", "Затронутые версии"),
        ("fix", "Обновление"),
        ("workaround", "Временные меры"),
        ("impact", "Последствия"),
        ("equipment", "Оборудование"),
        ("protocols", "Протоколы"),
    ):
        value = str(getattr(card, field))
        if value and not _figures_supported(value, allowed):
            updates[field] = ""
            removed.append(label)
    # A weakness named in the text or by the catalogue, whose text is in the evidence too.
    named = {value.upper() for value in _CWE_RE.findall(source)}
    cwe = tuple(dict.fromkeys(value.upper() for value in card.cwe if value.upper() in named))
    if len(cwe) < len(card.cwe):
        removed.append("CWE")
    updates["cwe"] = cwe
    evidence = exploit_evidence(_about(ids, source))
    if evidence != "unknown":
        updates["exploit"] = evidence
    elif card.exploit in ("in_the_wild", "public"):
        # An exploit the text does not mention would raise the priority on a guess.
        updates["exploit"] = "unknown"
        removed.append("Эксплойт")
    return card.model_copy(update=updates), removed


def _about(ids: Sequence[str], source: str) -> str:
    """The sentences that name the vulnerability, when the card has its ids and
    the text names them: a roundup of five CVEs says "exploited" of one."""
    # The text is about this vulnerability alone: all of it speaks of it.
    if not ids or not set(identifiers(source)) - set(ids):
        return source
    sentences = [
        sentence for sentence in split_sentences(source) if set(identifiers(sentence)) & set(ids)
    ]
    return " ".join(sentences) or source


# An ATT&CK id as an article prints it: "T1190", "T1021.003", or "T0817" of ICS.
_TECHNIQUE_ID_RE = re.compile(r"\bT[01]\d{3}(?:\.\d{3})?\b")
MAX_TECHNIQUES = 12


def technique_ids(text: str) -> list[str]:
    """The ATT&CK ids a text prints, in its order, without repeats."""
    return list(dict.fromkeys(_TECHNIQUE_ID_RE.findall(text)))


def _techniques(
    techniques: Sequence[AttackTechnique], source: str, known: Mapping[str, str] | None
) -> tuple[AttackTechnique, ...]:
    """The techniques that exist and that the text describes: by id, by
    ATT&CK's name or by the model's own words for it ("фишинг"). Without the
    reference only an id printed in the text is taken."""
    kept = []
    for technique in techniques:
        if known is None:
            if technique.id in source:
                kept.append(technique)
            continue
        name = known.get(technique.id)
        if name is None:
            continue
        if technique.id in source or _mentioned(name, source) or _mentioned(technique.name, source):
            kept.append(AttackTechnique(id=technique.id, name=name))
    if known is not None:
        # An id the article prints counts even when the model left it out; one
        # the reference lacks ("T1000" of a product's name) is no technique.
        named = {technique.id for technique in kept}
        kept += [
            AttackTechnique(id=value, name=known[value])
            for value in technique_ids(source)
            if value in known and value not in named
        ]
    return tuple(dict.fromkeys(kept))[:MAX_TECHNIQUES]


def _indicators(card: AttackCard, source: str) -> tuple[tuple[str, ...], bool]:
    """The model's indicators that the text has, then the rest of the text's;
    and whether the model gave one the text does not have."""
    in_text = extract_indicators(source)
    by_key = {refang(value): value for value in in_text}
    own = [by_key[refang(value)] for value in card.indicators if refang(value) in by_key]
    rest = [value for value in in_text if value not in own]
    return tuple(dict.fromkeys(own + rest)), len(own) < len(card.indicators)


def check_attack(
    card: AttackCard, source: str, techniques: Mapping[str, str] | None = None
) -> tuple[AttackCard, list[str]]:
    """`techniques` is the ATT&CK reference for the card's ids; None when it
    could not be asked."""
    removed: list[str] = []
    updates: dict[str, object] = {}
    # The model reads "energy_sector" by its name and leaves out industry it
    # wrote in the sectors itself; the rule takes the sectors' words.
    if not card.energy_sector and _ENERGY_OR_INDUSTRY_RE.search(card.sectors):
        updates["energy_sector"] = True
    if card.group and not _mentioned(card.group, source):
        updates["group"] = ""
        removed.append("Группировка")
    tools = tuple(tool for tool in card.tools if _mentioned(tool, source))
    if len(tools) < len(card.tools):
        updates["tools"] = tools
        removed.append("Инструменты")
    known = identifiers(source)
    ids = tuple(value for value in identifiers(" ".join(card.vulnerabilities)) if value in known)
    if len(ids) < len(card.vulnerabilities):
        removed.append("Уязвимости")
    updates["vulnerabilities"] = ids
    allowed = numbers(source)
    if card.attack_date and not _figures_supported(card.attack_date, allowed):
        updates["attack_date"] = ""
        removed.append("Дата атаки")
    if card.affected and not _figures_supported(card.affected, allowed):
        updates["affected"] = ""
        removed.append("Затронутые продукты")
    kept = _techniques(card.techniques, source, techniques)
    # Ids the article printed may stand in for a technique the check took out.
    if {technique.id for technique in card.techniques} - {technique.id for technique in kept}:
        removed.append("Техники ATT&CK")
    updates["techniques"] = kept
    indicators, invented = _indicators(card, source)
    updates["indicators"] = indicators
    if indicators:
        updates["iocs"] = True
    elif card.iocs and not _IOC_RE.search(source):
        updates["iocs"] = None
    if invented or (card.iocs and not indicators and not _IOC_RE.search(source)):
        removed.append("Индикаторы компрометации")
    return card.model_copy(update=updates), removed


def unsupported_figures(text: str, allowed: set[str]) -> set[str]:
    """Figures in model prose that neither the article nor the reader's profile has."""
    return numbers(text) - allowed


# --- Plain language for management -------------------------------------------

# What a manager is not given in the text: identifiers, scores, indicators,
# addresses and version numbers. The links to the details stay.
_TECHNICAL = [
    re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE),
    re.compile(r"\bBDU:\d{4}-\d{5}\b", re.IGNORECASE),
    re.compile(r"\b(?:CVSS|IoCs?|IOCs?)\b"),
    re.compile(r"\b(?:[a-f0-9]{64}|[a-f0-9]{40}|[a-f0-9]{32})\b", re.IGNORECASE),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
]
# Three numbers and more through dots; a date has the same shape and is no version.
_VERSION = re.compile(r"\b\d+(?:\.\d+){2,}\b")
_DATE = re.compile(r"^(?:[0-2]?\d|3[01])\.(?:0?\d|1[0-2])\.(?:\d{2}|\d{4})$")
PLAIN_SENTENCES = 2
PLAIN_LINE = 160


def technical_tokens(text: str) -> list[str]:
    """Technical details in a text for management, in the order found."""
    found: list[str] = []
    rest = text
    for pattern in _TECHNICAL:
        found += pattern.findall(rest)
        # An IP address is not counted again as a version.
        rest = pattern.sub(" ", rest)
    found += [match for match in _VERSION.findall(rest) if not _DATE.match(match)]
    return list(dict.fromkeys(found))


def _without_tokens(text: str) -> str:
    for token in technical_tokens(text):
        text = text.replace(token, "")
    text = re.sub(r"\(\s*[,;]?\s*\)", "", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def plain_brief(text: ItemSummary) -> ItemSummary:
    """A brief for management: two sentences at most, none with technical
    details; when every sentence has them, the first one without them."""
    sentences = split_sentences(text.summary)
    plain = [sentence for sentence in sentences if not technical_tokens(sentence)]
    if not plain and sentences:
        plain = [_without_tokens(sentences[0])]
    headline = _without_tokens(text.headline) if technical_tokens(text.headline) else text.headline
    return text.model_copy(
        update={
            "headline": headline,
            "summary": " ".join(plain[:PLAIN_SENTENCES]),
            "why": "" if technical_tokens(text.why) else text.why,
        }
    )


def _one_line(line: str) -> str:
    first = (split_sentences(line) or [""])[0].strip()
    if len(first) <= PLAIN_LINE:
        return first
    cut = first[: PLAIN_LINE - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{cut}…"


def plain_lines(lines: Sequence[str], limit: int) -> tuple[str, ...]:
    """Theses for management: one sentence each, no technical details."""
    kept = (_one_line(line) for line in lines if line.strip())
    return tuple(line for line in kept if line and not technical_tokens(line))[:limit]


# --- Links of a Telegram post -------------------------------------------------


_UNSAFE_IN_CODE = str.maketrans(
    {"`": "%60", " ": "%20", "\n": "%0A", "\r": "%0D", "\t": "%09", "<": "%3C", ">": "%3E"}
)


def defang(url: str) -> str:
    """ "https://github[.]com/x": readable, not clickable, as in the dataset.
    A post may point at a working exploit."""
    parts = urlsplit(url)
    if not parts.hostname:
        return url
    defanged = urlunsplit(parts._replace(netloc=parts.netloc.replace(".", "[.]")))
    # A backtick or a line break in the path would close a Markdown code span.
    return defanged.translate(_UNSAFE_IN_CODE)


# --- The whole entry -----------------------------------------------------------

_RUSSIA_RE = re.compile(r"Росси|\bРФ\b|российск|Russia", re.IGNORECASE)
_ENERGY_RE = re.compile(
    r"энергетик|электроэнергет|электросет|электростанц|подстанц|\bТЭК\b|нефтегаз|генерирующ|"
    r"energy sector|power grid|electric utilit",
    re.IGNORECASE,
)
# The dataset's "energy sector" of an attack takes industry in: PhantomCore's
# attack on Russian industry is a high-priority example there.
_ENERGY_OR_INDUSTRY_RE = re.compile(rf"{_ENERGY_RE.pattern}|промышлен|машиностро|завод", re.I)
_CVSS_SCORE_RE = re.compile(r"CVSS[^\d\n]{0,40}?(\d{1,2}[.,]\d)\b", re.IGNORECASE)
_CVSS_VECTOR_RE = re.compile(
    r"\b(?:CVSS:[34]\.\d/)?AV:[NALP]/AC:[LH]/(?:PR|Au):[NLHMS]/[A-Z:/]{10,40}[NLHPC]\b"
)
# Offline tags: words that mark each feature, checked in the article's text.
_TAG_RES: dict[ManagementTag, re.Pattern[str]] = {
    "energy": _ENERGY_RE,
    "industry": re.compile(r"промышлен|завод|машиностро|industrial|АСУ ТП|SCADA", re.I),
    "data_leak": re.compile(r"утечк|утекл|слив\w* данн|data leak|персональн\w+ данн", re.I),
    "financial_loss": re.compile(r"ущерб|убыт|выкуп|ransom|млрд|миллиард", re.I),
    "critical_infrastructure": re.compile(
        r"\bКИИ\b|критическ\w+ инфраструктур|critical infrastructure|парализ", re.I
    ),
    "government_law": re.compile(
        r"законопроект|\bзакон\b|ФСТЭК|Минцифр|регулятор|штраф|госорган|government", re.I
    ),
    "reputation": re.compile(r"репутац|имидж", re.I),
    "mass_service": re.compile(r"WhatsApp|Telegram|Android|iPhone|мессенджер|Госуслуг", re.I),
    "people_events": re.compile(r"конференц|форум|PHDays|SOC Forum|кадров\w* дефицит", re.I),
}


def source_text(title: str, summary: str, content: str | None) -> str:
    return "\n".join(part for part in (title, summary, content or "") if part)


def card_ids(text: ItemSummary, source: str) -> list[str]:
    """The ids a card is about: its own, or those of a text that names few."""
    if text.vulnerability is not None:
        named = list(text.vulnerability.ids)
    elif text.attack is not None:
        named = list(text.attack.vulnerabilities)
    else:
        return []
    known = identifiers(source)
    return identifiers(" ".join(named)) or (known if len(known) <= 3 else [])


def check_entry(
    text: ItemSummary, source: str, techniques: Mapping[str, str] | None = None
) -> ItemSummary:
    """The entry with every card field the article does not support taken out."""
    removed = list(text.unsupported)
    updates: dict[str, object] = {}
    if text.attack is not None:
        attack, lost = check_attack(text.attack, source, techniques)
        updates["attack"] = attack
        removed += lost
    if text.vulnerability is not None:
        vulnerability, lost = check_vulnerability(text.vulnerability, source)
        updates["vulnerability"] = vulnerability
        removed += lost
    if "ru" in text.tags and "abroad" in text.tags:
        drop = "abroad" if _RUSSIA_RE.search(source) else "ru"
        updates["tags"] = tuple(tag for tag in text.tags if tag != drop)
    updates["unsupported"] = tuple(dict.fromkeys(removed))
    return text.model_copy(update=updates)


def offline_vulnerability(source: str) -> VulnerabilityCard:
    """What a vulnerability card can hold without a model: ids, CVSS, exploit."""
    score = _CVSS_SCORE_RE.search(source)
    vector = _CVSS_VECTOR_RE.search(source)
    return VulnerabilityCard(
        ids=tuple(identifiers(source)[:5]),
        cvss_score=score.group(1).replace(",", ".") if score else "",
        cvss_vector=vector.group(0) if vector else "",
        exploit=exploit_evidence(source),
        cwe=tuple(dict.fromkeys(value.upper() for value in _CWE_RE.findall(source)))[:3],
    )


def offline_attack(source: str) -> AttackCard:
    return AttackCard(
        victim_in_russia=bool(_RUSSIA_RE.search(source)),
        energy_sector=bool(_ENERGY_OR_INDUSTRY_RE.search(source)),
        vulnerabilities=tuple(identifiers(source)[:5]),
        iocs=True if _IOC_RE.search(source) else None,
        indicators=tuple(extract_indicators(source)),
    )


def offline_tags(source: str) -> tuple[ManagementTag, ...]:
    place: ManagementTag = "ru" if _RUSSIA_RE.search(source) else "abroad"
    return (place, *(tag for tag, pattern in _TAG_RES.items() if pattern.search(source)))


def section_overview(kind: RecordKind, texts: list[ItemSummary | None]) -> str:
    """A line under a fixed section: how many entries of each priority."""
    counts = dict.fromkeys(PRIORITY_LABELS, 0)
    for text in texts:
        level = priority(kind, text)
        if level is not None:
            counts[level] += 1
    parts = [
        f"{PRIORITY_LABELS[level]} приоритет: {count}" for level, count in counts.items() if count
    ]
    rule = (
        "атака на энергетику или промышленность РФ выше атаки на другие отрасли РФ, "
        "атаки вне РФ ниже всех"
        if kind == "attack"
        else "уязвимость с эксплойтом выше уязвимости без него"
    )
    return f"{'; '.join(parts).capitalize()}. Порядок по правилу: {rule}."


def _flag(value: bool | None) -> str:
    return NO_DATA if value is None else ("есть" if value else "нет")


def attack_rows(card: AttackCard) -> list[tuple[str, str]]:
    """The attack card as the dataset's "desired output" lists it."""
    techniques = "; ".join(f"{item.id} {item.name}".strip() for item in card.techniques)
    return [
        ("Страна жертвы", card.victim_country or NO_DATA),
        ("Группировка", card.group or NO_DATA),
        ("Дата атаки", card.attack_date or NO_DATA),
        ("Отрасли и компании", card.sectors or NO_DATA),
        ("Вектор атаки", card.vector or NO_DATA),
        ("Первоначальный доступ", card.initial_access or NO_DATA),
        ("Затронутые продукты", card.affected or NO_DATA),
        ("Инструменты", ", ".join(card.tools) or NO_DATA),
        ("Уязвимости", ", ".join(card.vulnerabilities) or NO_DATA),
        ("Техники ATT&CK", techniques or NO_DATA),
        ("Индикаторы компрометации", ", ".join(card.indicators) or _flag(card.iocs)),
    ]


def vulnerability_rows(card: VulnerabilityCard) -> list[tuple[str, str]]:
    score = card.cvss_score
    cvss = (
        f"{score} ({card.cvss_vector})" if score and card.cvss_vector else score or card.cvss_vector
    )
    rows = [
        ("Уязвимость", card.name or NO_DATA),
        ("Затронуто", card.affected or NO_DATA),
        ("Обновление", card.fix or NO_DATA),
        ("Временные меры", card.workaround or NO_DATA),
        ("Эксплойт", EXPLOIT_LABELS[card.exploit]),
        ("Идентификаторы", ", ".join(card.ids) or NO_DATA),
        ("CVSS", cvss or NO_DATA),
        # The vector in words: from the network, with which rights, with a click.
        *parse_cvss_vector(card.cvss_vector),
        ("CWE", ", ".join(card.cwe) or NO_DATA),
        ("Последствия", card.impact or NO_DATA),
    ]
    # Industrial control systems only: there is nothing to say for the rest.
    if card.equipment:
        rows.append(("Оборудование", card.equipment))
    if card.protocols:
        rows.append(("Протоколы", card.protocols))
    return rows


def reference_rows(references: Sequence[VulnerabilityReference]) -> list[tuple[str, str]]:
    """What the reference bases said, one id after another, as a card row."""
    if not references:
        return []
    parts = []
    unknown = [reference.id for reference in references if not reference.found]
    for reference in (reference for reference in references if reference.found):
        facts = []
        if reference.kev_added is not None:
            kev = f"CISA KEV с {reference.kev_added:%d.%m.%Y}"
            if reference.kev_due is not None:
                kev += f", устранить до {reference.kev_due:%d.%m.%Y}"
            facts.append(kev)
        if reference.bdu_id:
            bdu = [reference.bdu_id]
            if reference.bdu_exploit:
                bdu.append(f"эксплойт {reference.bdu_exploit}")
            if reference.bdu_in_attacks:
                bdu.append("используется в атаках")
            facts.append(", ".join(bdu))
        if reference.nvd_exploitation == "active":
            facts.append("CISA SSVC: эксплуатируется")
        if reference.exploits:
            facts.append(f"эксплойт в Exploit-DB {reference.exploits[0]}")
        elif reference.nvd_exploit_links or reference.nvd_exploitation == "poc":
            facts.append("публичный эксплойт по NVD")
        if reference.epss is not None:
            facts.append(f"EPSS {reference.epss:.1%}".replace(".", ","))
        if reference.nvd_cvss and not reference.bdu_cvss:
            facts.append(f"CVSS {reference.nvd_cvss} по NVD")
        parts.append(f"{reference.id}: {'; '.join(facts)}")
    if unknown:
        parts.append(f"нет в справочных базах: {', '.join(unknown)}")
    return [("Сверено по базам", "; ".join(parts))]
