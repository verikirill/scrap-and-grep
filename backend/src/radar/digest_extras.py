"""What an issue adds beside its entries: the handwork it spares, a plan for a
specialist's shift, what changed for vulnerabilities seen in earlier issues,
and management's period in numbers.

Everything here is worked out from the entries and their cards, never written
by the model, so each line leads back to an entry and its article.
"""

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ValidationError

from radar.cards import EXPLOIT_LABELS, TAG_LABELS
from radar.domain import Exploit, ItemSummary, ManagementTag, RecordKind, VulnerabilityReference
from radar.fix_status import row_says_pending

if TYPE_CHECKING:
    from radar.views import ItemView

# The handwork an issue replaces, by a rule stated wherever the number is
# shown: a headline glanced at in a feed reader, an entry written with its
# card and link. Both are assumptions until the analyst comparison is run.
SECONDS_PER_HEADLINE = 5
MINUTES_PER_ENTRY = 3
# A checklist a shift gets through, not the whole issue again.
PLAN_SIZE = 8
PLAN_INDICATORS = 5
PLAN_TECHNIQUES = 3
# How far back a vulnerability counts as one the reader has already seen.
HISTORY_DAYS = 30
HISTORY_ISSUES = 10
NUMBERS_SIZE = 8
# The day of an issue as its reader sees it.
MOSCOW = ZoneInfo("Europe/Moscow")
# Thousands kept on one line: «1 783 публикации».
NBSP = chr(0xA0)

_EXPLOIT_RANK: dict[Exploit, int] = {"unknown": 0, "none": 0, "public": 1, "in_the_wild": 2}


class ManualWork(BaseModel):
    """The issue's work as an analyst would do it by hand."""

    headlines: int
    entries: int
    minutes: int
    # How long the assistant took, when the build recorded it.
    seconds: float | None = None


class PlanEntry(BaseModel):
    headline: str
    url: str
    kind: RecordKind
    # What to do, taken from the card: the update, the workaround, the way in
    # to check, the indicators to hunt for.
    steps: list[str]
    # Why it is urgent: the CISA catalogue and its deadline, EPSS, CVSS.
    facts: list[str]


class Change(BaseModel):
    """A vulnerability an earlier issue had, and what is new about it."""

    id: str
    headline: str
    url: str
    since: date
    what: list[str]


class TagCount(BaseModel):
    tag: ManagementTag
    label: str
    count: int
    # In the previous issue of the same length, when there is one.
    before: int | None = None


def _count(value: object) -> float:
    """A number from the stats a build wrote; anything else counts as none."""
    return float(value) if isinstance(value, (int, float)) and value > 0 else 0.0


def manual_work(stats: Mapping[str, Any]) -> ManualWork | None:
    headlines = int(_count(stats.get("window_total")))
    if headlines == 0:
        return None
    entries = int(_count(stats.get("selected")))
    minutes = round(headlines * SECONDS_PER_HEADLINE / 60 + entries * MINUTES_PER_ENTRY)
    seconds = _count(stats.get("duration_seconds"))
    return ManualWork(
        headlines=headlines, entries=entries, minutes=minutes, seconds=seconds or None
    )


def _plural(count: int, forms: tuple[str, str, str]) -> str:
    tail = count % 100
    if 11 <= tail <= 14:
        return forms[2]
    if count % 10 == 1:
        return forms[0]
    return forms[1] if 2 <= count % 10 <= 4 else forms[2]


def _number(value: int) -> str:
    return f"{value:,}".replace(",", NBSP)


def duration_words(minutes: int) -> str:
    """ "52 мин", "1,5 ч", "12 ч": a span read at a glance."""
    if minutes < 90:
        return f"{minutes} мин"
    hours = round(minutes / 60, 1)
    return f"{hours:g} ч".replace(".", ",") if hours < 10 else f"{round(hours)} ч"


def manual_line(work: ManualWork) -> str:
    """One sentence for the head of an issue, the rule included."""
    forms = ("публикацию", "публикации", "публикаций")
    headlines = f"{_number(work.headlines)} {_plural(work.headlines, forms)}"
    entries = f"{work.entries} {_plural(work.entries, ('запись', 'записи', 'записей'))}"
    took = f" за {round(work.seconds)} с" if work.seconds else ""
    return (
        f"ассистент просмотрел {headlines} и написал {entries}{took}; вручную это около "
        f"{duration_words(work.minutes)} при {SECONDS_PER_HEADLINE} с на заголовок "
        f"и {MINUTES_PER_ENTRY} мин на запись"
    )


def _day(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _percent(value: float) -> str:
    return f"{value:.1%}".replace(".", ",")


def _kev(references: Sequence[VulnerabilityReference]) -> str:
    listed = [ref for ref in references if ref.kev_added is not None]
    if not listed:
        return ""
    first = min(listed, key=lambda ref: ref.kev_added or date.max)
    due = f", устранить до {_day(first.kev_due)}" if first.kev_due else ""
    return f"в каталоге CISA KEV с {_day(first.kev_added or date.max)}{due}"


def _epss(references: Sequence[VulnerabilityReference]) -> float | None:
    scores = [ref.epss for ref in references if ref.epss is not None]
    return max(scores) if scores else None


def _vulnerability_entry(item: ItemView) -> PlanEntry:
    card = item.vulnerability
    references = item.references
    update = [f"Обновление: {card.fix}"] if card is not None and card.fix else []
    workaround = (
        [f"Временные меры: {card.workaround}"] if card is not None and card.workaround else []
    )
    # An update that is not out is no step for today's shift: the workaround is.
    pending = card is not None and row_says_pending(card.fix)
    steps = [*workaround, *update] if pending else [*update, *workaround]
    if not steps:
        steps += [f"Устранение по БДУ: {ref.bdu_fix}" for ref in references if ref.bdu_fix][:1]
    facts = [kev] if (kev := _kev(references)) else []
    if (epss := _epss(references)) is not None:
        facts.append(f"EPSS {_percent(epss)}")
    score = (card.cvss_score if card else "") or next(
        (ref.nvd_cvss or ref.bdu_cvss for ref in references if ref.nvd_cvss or ref.bdu_cvss), ""
    )
    if score:
        facts.append(f"CVSS {score}")
    if card is not None and card.exploit in ("in_the_wild", "public"):
        facts.append(f"эксплойт: {EXPLOIT_LABELS[card.exploit]}")
    return PlanEntry(
        headline=item.headline, url=item.url, kind="vulnerability", steps=steps, facts=facts
    )


def _attack_entry(item: ItemView) -> PlanEntry:
    card = item.attack
    steps = []
    facts = []
    if card is not None:
        if card.initial_access:
            steps.append(f"Проверить первоначальный доступ: {card.initial_access}")
        if card.indicators:
            steps.append(f"Поискать индикаторы: {', '.join(card.indicators[:PLAN_INDICATORS])}")
        if card.techniques:
            named = (f"{tech.id} {tech.name}".strip() for tech in card.techniques)
            steps.append(f"Техники для правил: {', '.join(list(named)[:PLAN_TECHNIQUES])}")
        if card.vulnerabilities:
            steps.append(f"Закрыть уязвимости: {', '.join(card.vulnerabilities)}")
        facts += [part for part in (card.group, card.sectors) if part]
    return PlanEntry(headline=item.headline, url=item.url, kind="attack", steps=steps, facts=facts)


def shift_plan(items: Iterable[ItemView]) -> list[PlanEntry]:
    """The high-priority attacks and vulnerabilities as a checklist: exploited
    vulnerabilities first, by EPSS, then attacks. An entry whose card gives
    nothing to do or check is left to the issue itself."""
    urgent = [
        item
        for item in items
        if item.priority == "high" and item.kind in ("vulnerability", "attack")
    ]

    def order(item: ItemView) -> tuple[int, int, float]:
        listed = any(ref.kev_added for ref in item.references)
        return (item.kind != "vulnerability", not listed, -(_epss(item.references) or 0.0))

    plan = []
    for item in sorted(urgent, key=order):
        entry = _vulnerability_entry(item) if item.kind == "vulnerability" else _attack_entry(item)
        if entry.steps or entry.facts:
            plan.append(entry)
    return plan[:PLAN_SIZE]


class VulnerabilityState(BaseModel):
    """What one issue knew of a vulnerability."""

    id: str
    headline: str
    url: str
    day: date
    exploit: Exploit
    kev_added: date | None = None
    fixed: bool = False


def vulnerability_states(
    entries: Iterable[tuple[ItemSummary, str, str, datetime]],
) -> dict[str, VulnerabilityState]:
    """The vulnerabilities of some entries by id: (text, headline, url, when).

    What any entry knew is kept: a later article with a thinner card does not
    take the catalogue or the exploit back. The headline and the day are the
    latest entry's."""
    states: dict[str, VulnerabilityState] = {}
    for text, headline, url, when in sorted(entries, key=lambda entry: entry[3]):
        card = text.vulnerability
        if card is None:
            continue
        references = {ref.id: ref for ref in text.references}
        for identifier in dict.fromkeys([*card.ids, *references]):
            reference = references.get(identifier)
            state = VulnerabilityState(
                id=identifier,
                headline=headline,
                url=url,
                day=when.astimezone(MOSCOW).date(),
                exploit=card.exploit,
                kev_added=reference.kev_added if reference else None,
                # An update the row calls not out yet is no fix. Neither is BDU's
                # "обновление программного обеспечения", written before any
                # fixed build exists, nor NVD's "Patch" tag on an advisory: with
                # them a vulnerability counted as fixed from its first issue, and
                # the day its update really came out was never reported.
                fixed=bool(card.fix) and not row_says_pending(card.fix),
            )
            states[identifier] = _merged(states.get(identifier), state)
    return states


def _merged(known: VulnerabilityState | None, new: VulnerabilityState) -> VulnerabilityState:
    if known is None:
        return new
    listed = [day for day in (known.kev_added, new.kev_added) if day is not None]
    exploit = max(known.exploit, new.exploit, key=_EXPLOIT_RANK.__getitem__)
    return new.model_copy(
        update={
            "exploit": exploit,
            "kev_added": min(listed) if listed else None,
            "fixed": known.fixed or new.fixed,
        }
    )


def stored_changes(raw: object) -> list[Change]:
    """The changes a build kept in its stats; a row that does not read is skipped
    rather than taking the whole issue down."""
    found = []
    for row in raw if isinstance(raw, list) else []:
        try:
            found.append(Change.model_validate(row))
        except ValidationError:
            continue
    return found


def changes(
    earlier: Mapping[str, VulnerabilityState], now: Mapping[str, VulnerabilityState]
) -> list[Change]:
    """What became known about vulnerabilities an earlier issue already had:
    into the CISA catalogue, an exploit appeared or grew, an update came out."""
    found = []
    for identifier, state in now.items():
        before = earlier.get(identifier)
        if before is None:
            continue
        what = []
        if state.kev_added and not before.kev_added:
            what.append(f"попала в каталог CISA KEV {_day(state.kev_added)}")
        if _EXPLOIT_RANK[state.exploit] > _EXPLOIT_RANK[before.exploit]:
            what.append(
                f"эксплойт: было «{EXPLOIT_LABELS[before.exploit]}», "
                f"стало «{EXPLOIT_LABELS[state.exploit]}»"
            )
        if state.fixed and not before.fixed:
            what.append("вышло обновление или мера устранения")
        if what:
            found.append(
                Change(
                    id=identifier,
                    headline=state.headline,
                    url=state.url,
                    since=before.day,
                    what=what,
                )
            )
    return found


def tag_counts(texts: Iterable[ItemSummary | None]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for text in texts:
        for tag in text.tags if text else ():
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def period_numbers(items: Iterable[ItemView], before: Mapping[str, int] | None) -> list[TagCount]:
    """Entries per dataset tag, with the previous issue's count beside them."""
    counts: dict[ManagementTag, int] = {}
    for item in items:
        for tag in item.tags:
            counts[tag] = counts.get(tag, 0) + 1
    tags = [tag for tag in TAG_LABELS if counts.get(tag) or (before or {}).get(tag)]
    rows = [
        TagCount(
            tag=tag,
            label=TAG_LABELS[tag],
            count=counts.get(tag, 0),
            before=(before or {}).get(tag, 0) if before is not None else None,
        )
        for tag in tags
    ]
    return sorted(rows, key=lambda row: -row.count)[:NUMBERS_SIZE]


def numbers_title(start: datetime, end: datetime) -> str:
    days = round((end - start).total_seconds() / 86400)
    if days == 1:
        return "Сутки в цифрах"
    if days == 7:
        return "Неделя в цифрах"
    if 28 <= days <= 31:
        return "Месяц в цифрах"
    return "Период в цифрах"
