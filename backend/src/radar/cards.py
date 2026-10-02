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
from collections.abc import Sequence
from urllib.parse import urlsplit, urlunsplit

from radar.domain import (
    AttackCard,
    Exploit,
    ItemSummary,
    ManagementTag,
    Priority,
    RecordKind,
    VulnerabilityCard,
    VulnerabilityReference,
)
from radar.text import numbers, split_sentences

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
    ):
        value = str(getattr(card, field))
        if value and not _figures_supported(value, allowed):
            updates[field] = ""
            removed.append(label)
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


def check_attack(card: AttackCard, source: str) -> tuple[AttackCard, list[str]]:
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
    if card.iocs and not _IOC_RE.search(source):
        updates["iocs"] = None
        removed.append("Индикаторы компрометации")
    return card.model_copy(update=updates), removed


def unsupported_figures(text: str, allowed: set[str]) -> set[str]:
    """Figures in model prose that neither the article nor the reader's profile has."""
    return numbers(text) - allowed


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


def check_entry(text: ItemSummary, source: str) -> ItemSummary:
    """The entry with every card field the article does not support taken out."""
    removed = list(text.unsupported)
    updates: dict[str, object] = {}
    if text.attack is not None:
        attack, lost = check_attack(text.attack, source)
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
    )


def offline_attack(source: str) -> AttackCard:
    return AttackCard(
        victim_in_russia=bool(_RUSSIA_RE.search(source)),
        energy_sector=bool(_ENERGY_OR_INDUSTRY_RE.search(source)),
        vulnerabilities=tuple(identifiers(source)[:5]),
        iocs=True if _IOC_RE.search(source) else None,
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
    return [
        ("Страна жертвы", card.victim_country or NO_DATA),
        ("Группировка", card.group or NO_DATA),
        ("Дата атаки", card.attack_date or NO_DATA),
        ("Отрасли и компании", card.sectors or NO_DATA),
        ("Первоначальный доступ", card.initial_access or NO_DATA),
        ("Инструменты", ", ".join(card.tools) or NO_DATA),
        ("Уязвимости", ", ".join(card.vulnerabilities) or NO_DATA),
        ("Индикаторы компрометации", _flag(card.iocs)),
    ]


def vulnerability_rows(card: VulnerabilityCard) -> list[tuple[str, str]]:
    score = card.cvss_score
    cvss = (
        f"{score} ({card.cvss_vector})" if score and card.cvss_vector else score or card.cvss_vector
    )
    return [
        ("Уязвимость", card.name or NO_DATA),
        ("Затронуто", card.affected or NO_DATA),
        ("Обновление", card.fix or NO_DATA),
        ("Временные меры", card.workaround or NO_DATA),
        ("Эксплойт", EXPLOIT_LABELS[card.exploit]),
        ("Идентификаторы", ", ".join(card.ids) or NO_DATA),
        ("CVSS", cvss or NO_DATA),
        ("Последствия", card.impact or NO_DATA),
    ]


def reference_rows(references: Sequence[VulnerabilityReference]) -> list[tuple[str, str]]:
    """What the reference bases said, one id after another, as a card row."""
    if not references:
        return []
    parts = []
    unknown = [reference.id for reference in references if not reference.found]
    for reference in (reference for reference in references if reference.found):
        facts = []
        if reference.kev_added is not None:
            facts.append(f"CISA KEV с {reference.kev_added:%d.%m.%Y}")
        if reference.bdu_id:
            bdu = [reference.bdu_id]
            if reference.bdu_exploit:
                bdu.append(f"эксплойт {reference.bdu_exploit}")
            if reference.bdu_in_attacks:
                bdu.append("используется в атаках")
            facts.append(", ".join(bdu))
        parts.append(f"{reference.id}: {'; '.join(facts)}")
    if unknown:
        parts.append(f"нет в CISA KEV и БДУ: {', '.join(unknown)}")
    return [("Сверено по базам", "; ".join(parts))]
