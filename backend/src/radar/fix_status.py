"""Whether a vulnerability's fix is out, and advice that agrees with it.

A card can say "обновления пока недоступны" in its update row while "Почему
важно" tells the reader to install the patch: the model writes both fields in
one answer and nothing tied them together. The rule here is deterministic and
runs past the answer cache, like the check of a card: the article and the
card's own update row decide whether the fix is out, never the reference
bases. BDU writes "Способ устранения: обновление программного обеспечения"
the day a vulnerability is published, before any fixed build exists, and NVD
tags a vendor advisory "Patch" whether or not it ships one.

A fix taken for missing when it is out costs the reader good advice, so a
phrase counts only when the article says it of the fix, within one clause:
"обновления пока недоступны", not "уязвимость в прошивке делает их
недоступными" or "патч выпущен, но пока не все его установили". "До выхода
исправлений" does not count either: it tells as often of attacks before a
release that came since.
"""

import re
from typing import Literal

from radar.cards import identifiers
from radar.domain import ItemSummary, VulnerabilityCard
from radar.text import split_sentences

FixStatus = Literal["pending", "partial", ""]
# More ids than a story about one vulnerability names (selection's FOCUSED_IDS).
ROUNDUP_IDS = 4

# One sentence, where the dots of a version ("7.4.9") do not end it.
_IN_SENTENCE = r"(?:[^.!?\n]|(?<=\d)\.(?=\d))"
# The fix as articles name it: "обновления", "исправление", "патч",
# "исправленные версии", "исправленных прошивок". Firmware alone is the product.
# A fix word that depends on another is not what the sentence speaks of: a
# virtual patch is a filter's rule, and "после установки обновления ожидается
# перезагрузка" awaits the reboot.
_DEPENDENT = (
    r"(?<!виртуального\s)(?<!виртуальных\s)(?<!после\s)(?<!установки\s)(?<!применения\s)"
    r"(?<!выхода\s)"
)
_FIX = rf"{_DEPENDENT}(?:обновлени|исправлени|патч|исправленн\w*\s+(?:верси|прошив|сбор))\w*"
_FIX_OR_VERSION = rf"(?:{_FIX}|верси\w*)"
_FIX_EN = r"(?:(?:security\s+)?updates?|patch(?:es)?|fix(?:es)?|(?:patched|fixed)\s+versions?)"
# Up to three words between the fix and what is said of it. A comma or a
# semicolon opens another clause, which may speak of something else.
_GAP = r"\s+(?:(?:[\w-]+|\d+(?:\.\d+)+)\s+){0,3}?"
# Said of the fix: "пока недоступны", "ещё готовятся", "пока не выпустила".
# "Недоступны" in its short form only: "делает контроллер недоступным" is a
# denial of service, whoever causes it.
_NOT_OUT = (
    r"(?:(?:пока|ещё|еще)\s+)?(?:не\s*доступн(?:ы|о|а|ен)\b|не\s+(?:выпущ|вышл|вышел|выйд|выпуст)|"
    r"готов[ия]тся|ожида[ею]тся)|в\s+разработке|будут?\s+выпущ|предстоящ"
)
# The article says the vendor has not shipped the fix yet. The phrasings are
# the snapshot's (data/samples): "обновления пока недоступны", "Исправления на
# момент публикации ещё готовятся", "Готовых обновлений на дату публикации
# нет", "Пока версия 4.23.0.0 не вышла", "Вторая выйдет только в четвёртом
# квартале", "security updates are not yet available", "... as upcoming".
_ARTICLE_PENDING_RE = re.compile(
    "|".join(
        [
            rf"{_FIX}{_GAP}(?:{_NOT_OUT})",
            rf"{_FIX}\s+(?:(?:пока|ещё|еще)\s+)?нет\b",
            # "Исправления вендор обещает в версиях ...", not "обновление обещает закрыть".
            rf"{_FIX}\s+(?:[\w-]+\s+){{1,2}}обещ",
            rf"(?:пока|до\s+тех\s+пор,?\s+пока)\s+не\s+(?:появ|выйд|выпуст)\w*\s+(?:[\w-]+\s+)?"
            rf"{_FIX_OR_VERSION}",
            rf"пока\s+{_FIX_OR_VERSION}\s+(?:\S+\s+){{0,2}}?не\s+(?:вышл|вышел|выпущ|выйд|появ|выпуст)",
            rf"(?:пока|ещё|еще)\s+(?:нет\s+(?:[\w-]+\s+)?{_FIX}|{_FIX}\s+нет\b)",
            rf"готов\w*\s+{_FIX}{_IN_SENTENCE}{{0,40}}?\bнет\b",
            r"предстоящ\w*\s+(?:верси|обновлени|исправлени|патч|релиз|выпуск)",
            r"выйд\w*\s+(?:только\s+)?(?:в|во|к)\s+(?:\w+\s+){0,2}?"
            r"(?:квартал|полугоди|году|месяц|недел)",
            r"жд\w*\s+(?:релиза|выпуска|выхода)",
            rf"(?:обещ|планиру)\w*\s+(?:выпустить|выпуск\w*)\s+(?:[\w-]+\s+)?{_FIX}",
            rf"{_FIX_EN}\s+(?:(?:is|are|have|has|was|were)\s+)?not\s+(?:yet\s+)?(?:been\s+)?"
            r"(?:available|released|out)\b",
            r"(?:yet\s+to\s+|(?:has|have)\s+not\s+(?:yet\s+)?)(?:release|ship|issue|publish)\w*\s+"
            r"(?:an?\s+|the\s+|any\s+)?(?:security\s+)?(?:patch|fix|update)",
            rf"until\s+(?:a\s+|the\s+)?{_FIX_EN}\s+(?:is|are|becomes?|gets?)\s+(?:made\s+)?"
            r"(?:available|released|out)\b",
            rf"no\s+(?:[\w-]+\s+)?{_FIX_EN}\s+(?:(?:is|are)\s+)?(?:yet\s+)?(?:available|released)|"
            r"no\s+(?:patch|fix)(?:es)?\s+yet",
            r"as\s+[\"“«]?(?:upcoming|forthcoming)",
            r"(?:upcoming|forthcoming)\s+(?:[\w-]+\s+)?(?:versions?|patch(?:es)?|fix(?:es)?|updates?)\b",
        ]
    ),
    re.IGNORECASE,
)
# The article says a fix is out: "It released fixes for both", "Скачать
# исправления можно установщиком CODESYS", "Cisco выпустила обновления".
_ARTICLE_RELEASED_RE = re.compile(
    r"released\s+(?:\w+\s+){0,2}(?:fix|patch|update)|(?:fix|patch|update)\w*\s+(?:is|are|were|was)\s+"
    r"(?:now\s+)?available|выпустил\w*\s+(?:\w+\s+){0,2}(?:исправлени|обновлени|патч)|"
    r"(?:исправлени|обновлени|патч)\w*\s+(?:уже\s+)?(?:выпущен|вышл|вышел|(?<!не)доступн)|"
    r"скачать\s+исправлени",
    re.IGNORECASE,
)
# The card's update row, a few words: "(пока недоступно, ожидается)",
# "(будут выпущены)", "в текущем выпуске исправления нет", "когда они станут
# доступны". "Пока нет данных" knows nothing of the fix, and "если доступно"
# hedges without saying it is missing.
_ROW_PENDING_RE = re.compile(
    r"недоступн|не\s+доступн|не\s+выпущ|не\s+выпуст|не\s+вышл|не\s+вышел|"
    r"(?:ещё|еще|пока)\s+не\s+(?:выпущ|вышл|вышел|доступ|опубликов|выпуст)|"
    r"пока\s+нет\b(?!\s+(?:данных|сведени|информаци))|"
    r"нет\s+(?:исправлен|обновлен|патч)|(?:исправлени|обновлени|патч)\w*\s+(?:ещё\s+|пока\s+)?нет|"
    r"готов[ия]тся|ожида[ею]тся|предстоящ|будут?\s+выпущ|в\s+разработке|upcoming|"
    r"если\s+(?:будет|появ|выйд)|когда\s+(?:\w+\s+){0,2}(?:выйд|появ|станут|будут)|"
    r"после\s+(?:выхода|публикации|выпуска)",
    re.IGNORECASE,
)
# Advice to install a patch or an update now: "установите патч", "обновите
# FortiMail", "необходимость немедленного обновления". A version said to be
# installed ("установлена уязвимая версия") is no advice.
_PATCH_ADVICE_RE = re.compile(
    r"(?:установ(?:ить|ите|ка|ку|ив)|постав(?:ить|ьте)|примен(?:ить|ите|ять|яйте|ени\w*)|накат\w*)"
    r"\s+(?:[\w.-]+\s+){0,3}?(?:патч|обновлени|исправлени|прошивк|верси)|"
    r"\bобнов(?:ите|ить|иться|итесь|ляйте|лять)\b|"
    r"(?:необходим|требу|нужн)\w*\s+(?:(?:немедленн|срочн|скорейш|своевременн)\w*\s+)?"
    r"(?:обновлени|установк)",
    re.IGNORECASE,
)
# Advice tied to the release agrees with "not out yet": "после выхода",
# "до установки обновлений", "планировать обновление", "если он доступен".
# Another condition ("если интерфейс доступен из интернета") does not tie it.
_TIED_TO_RELEASE_RE = re.compile(
    r"после\s+(?:выход|публикаци|выпуск|появлени)|как\s+только|по\s+мере\s+выход|"
    r"когда\s+(?:\w+\s+){0,2}?(?:выйд|появ|станет|станут)|"
    r"до\s+(?:выхода|установки|появлени)|пока\s+не\s+(?:появ|выйд|выпуст)|"
    r"если\s+(?:(?:он|она|оно|они|обновлени\w*|исправлени\w*|патч\w*)\s+)?(?:уже\s+)?"
    r"(?:доступ|выпущ|вышл|вышел|выйд|появ)|"
    r"(?:планир|подготов)\w*\s+(?:к\s+)?(?:\w+\s+){0,2}?(?:обновлени|установк|патч|исправлени)",
    re.IGNORECASE,
)
# The card prompt's "выпущено, версия ..." with what follows the claim.
_ROW_RELEASED_RE = re.compile(r"^\s*выпущено\b[\s,:;.-]*", re.IGNORECASE)
# A workaround row that names none: "Нет указанных временных мер защиты", "N/A".
_NO_WORKAROUND_RE = re.compile(r"(?:нет\b|n/?a\b|не\s+(?:указан|назван|приведен))", re.I)

PENDING_NOTE = "Исправление ещё не выпущено."
PARTIAL_NOTE = "Для части версий исправление ещё не выпущено."
# How the entry says what the rule changed, beside the fields the check took out.
ADVICE_REPLACED = "совет поставить исправление, которого ещё нет"


def row_says_pending(row: str) -> bool:
    """The update row of a card says the fix is not out."""
    return bool(_ROW_PENDING_RE.search(row))


def _about(card: VulnerabilityCard, article: str) -> str:
    """The article, or in a roundup of many vulnerabilities the sentences that
    name the card's own: what one says of its fix is not said of the others.
    A card no sentence names has nothing to go by."""
    if len(identifiers(article)) <= ROUNDUP_IDS:
        return article
    own = set(card.ids)
    return " ".join(
        sentence for sentence in split_sentences(article) if own & set(identifiers(sentence))
    )


def fix_status(card: VulnerabilityCard, article: str) -> FixStatus:
    """ "pending" when the card's update row or the article says the fix is not
    out, "partial" when the article also says a fix is out (one branch fixed,
    another waiting), "" when nothing says it is missing.

    A story about one vulnerability names its fix without the id ("Для
    затронутых установок FortiMail 7.4, 7.6 и 8.0 обновления пока недоступны").
    """
    article = _about(card, article)
    pending = row_says_pending(card.fix) or bool(_ARTICLE_PENDING_RE.search(article))
    if not pending:
        return ""
    released = any(
        _ARTICLE_RELEASED_RE.search(sentence) and not _ARTICLE_PENDING_RE.search(sentence)
        for sentence in split_sentences(article)
    )
    return "partial" if released else "pending"


def advises_patch(text: str) -> bool:
    """A sentence tells to install a patch or an update now, not after its release."""
    return any(
        _PATCH_ADVICE_RE.search(sentence) and not _TIED_TO_RELEASE_RE.search(sentence)
        for sentence in split_sentences(text)
    )


def _lower_first(text: str) -> str:
    """ "Отключить IBE" -> "отключить IBE"; a name in Latin letters or an
    abbreviation ("Fortinet предоставил...", "ФСТЭК") stays as it is."""
    first, second = text[:1], text[1:2]
    if ("А" <= first <= "Я" or first == "Ё") and not second.isupper():
        return first.lower() + text[1:]
    return text


def pending_advice(workaround: str) -> str:
    """What to do while there is no fix: the card's own workaround, checked
    against the article like every card field, or waiting for the vendor."""
    if workaround and not _NO_WORKAROUND_RE.match(workaround.strip()):
        steps = _lower_first(workaround.strip().rstrip("."))
        return f"Исправление ещё не выпущено, до его выхода: {steps}."
    return "Исправление ещё не выпущено: следите за выходом обновления у производителя."


def _restate_row(fix: str, status: FixStatus) -> str:
    """The update row saying what the article says of the fix. A row that calls
    the fix out ("Выпущено, версия 7.4.9") is true of the fixed branch when it
    is partial and gets the caveat; when nothing is out, the claim goes."""
    note = PENDING_NOTE if status == "pending" else PARTIAL_NOTE
    if not fix:
        return note
    if row_says_pending(fix):
        return fix
    claim = _ROW_RELEASED_RE.match(fix)
    if status == "pending" and claim:
        versions = fix[claim.end() :].rstrip(" .")
        return f"Ещё не выпущено: {versions}." if versions else note
    # The versions the vendor names stay, and the reader learns they are not
    # out. A sentence of its own: in brackets after "для ветки 7.2 перейти на
    # 7.4" it read as said of that move, which is out.
    return f"{fix.rstrip(' .')}. {note}"


def reconcile_fix(text: ItemSummary, article: str) -> ItemSummary:
    """The vulnerability entry with its update row and its advice agreeing on
    whether the fix is out.

    Not out at all: the row says so, and advice to install it gives way to
    the workaround. Out for some versions only: the row and the advice get
    that caveat, the advice for the fixed versions stays.
    """
    card = text.vulnerability
    if card is None:
        return text
    status = fix_status(card, article)
    if not status:
        return text
    fix = _restate_row(card.fix, status)
    why = text.why
    removed = list(text.unsupported)
    if advises_patch(why):
        if status == "pending":
            why = pending_advice(card.workaround)
            removed.append(ADVICE_REPLACED)
        elif PARTIAL_NOTE not in why:
            why = f"{why.rstrip()} {PARTIAL_NOTE}".strip()
    return text.model_copy(
        update={
            "why": why,
            "vulnerability": card.model_copy(update={"fix": fix}),
            "unsupported": tuple(dict.fromkeys(removed)),
        }
    )
