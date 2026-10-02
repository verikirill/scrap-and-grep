"""Render a digest as Markdown."""

import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from radar.cards import (
    KIND_LABELS,
    PRIORITY_LABELS,
    TAG_LABELS,
    defang,
)
from radar.views import DigestView, ItemView

MOSCOW = ZoneInfo("Europe/Moscow")

REJECT_REASONS = {
    "low_score": "ниже порога релевантности",
    "excluded": "попадает под исключение",
    "duplicate": "повтор уже включённой новости",
    "over_limit": "не вошла в лимит выпуска",
}


def format_date(value: datetime) -> str:
    return value.astimezone(MOSCOW).strftime("%d.%m.%Y")


def format_datetime(value: datetime) -> str:
    return value.astimezone(MOSCOW).strftime("%d.%m.%Y %H:%M")


_MARKDOWN_SPECIALS = str.maketrans(
    {"\\": "\\\\", "[": "\\[", "]": "\\]", "<": "&lt;", ">": "&gt;", "`": "\\`", "\n": " "}
)
_URL_UNSAFE = str.maketrans(
    {"(": "%28", ")": "%29", " ": "%20", "<": "%3C", ">": "%3E", '"': "%22", "\\": "%5C"}
)


def _escape(text: str) -> str:
    """Neutralise Markdown and HTML syntax in text that came from outside.

    Headlines, summaries and topic names originate in third-party articles or
    in model output. None of them may introduce a link, an image or a tag of
    its own into the exported file.
    """
    return text.translate(_MARKDOWN_SPECIALS).strip()


def _link(text: str, url: str) -> str:
    safe_url = "".join(ch for ch in url if ch.isprintable()).translate(_URL_UNSAFE)
    return f"[{_escape(text)}]({safe_url})"


def methodology(digest: DigestView) -> list[str]:
    """Short, factual notes on how this particular digest was produced."""
    stats = digest.stats
    lines = [
        f"Публикаций за период: {stats.get('window_total', 0)}. "
        f"Кандидатов после поиска по интересам: {stats.get('candidates', 0)}. "
        f"В выпуске: {stats.get('selected', 0)} из {stats.get('sources', 0)} источников.",
        f"Поиск: {stats.get('embedding_model', 'н/д')}"
        + (
            " (только полнотекстовый, модель эмбеддингов недоступна)"
            if stats.get("lexical_only")
            else ""
        )
        + f". Оценка и тексты: {stats.get('llm', 'н/д')}.",
    ]
    if stats.get("duplicates_merged"):
        lines.append(f"Пересказов одной новости объединено: {stats['duplicates_merged']}.")
    priorities = stats.get("priorities") or {}
    if any(priorities.values()):
        lines.append(
            "Приоритеты атак и уязвимостей по правилам датасета организаторов: "
            + ", ".join(
                f"{PRIORITY_LABELS[level]} {priorities.get(level, 0)}"
                for level in ("high", "medium", "low")
            )
            + "."
        )
    if "unsupported_fields" in stats:
        lines.append(
            "Проверка записей по тексту статей: исправлено записей "
            f"{stats.get('entries_corrected', 0)}, убрано полей и фраз "
            f"{stats.get('unsupported_fields', 0)}."
        )
    if stats.get("degraded"):
        lines.append(
            "Часть записей обработана резервным алгоритмом без языковой модели: "
            f"оценено моделью {stats.get('graded_by_model', 0)} из {stats.get('candidates', 0)}, "
            f"написано моделью {stats.get('written_by_model', 0)} из {stats.get('selected', 0)}."
        )
    return lines


def item_meta(item: ItemView) -> list[str]:
    """The line under an entry's headline: source, date, kind and priority, score."""
    meta = [item.source_name, format_date(item.published_at)]
    if item.priority:
        # Only a specialist's card has a kind and a priority to show.
        meta.append(KIND_LABELS[item.kind])
        reason = f" ({item.priority_reason})" if item.priority_reason else ""
        meta.append(f"приоритет: {PRIORITY_LABELS[item.priority]}{reason}")
    meta.append(f"релевантность {item.score:.2f}")
    if item.interest_title:
        meta.append(f"интерес: {item.interest_title}")
    return meta


def card_rows(item: ItemView) -> list[tuple[str, str]]:
    """The fields of the dataset's card, when the entry has one."""
    return [(field.label, field.value) for field in item.fields]


def _item(item: ItemView) -> list[str]:
    meta = " · ".join(_escape(part) for part in item_meta(item))
    lines = [f"### {_link(item.headline, item.url)}", "", f"*{meta}*", ""]
    if item.headline != item.title:
        lines += [f"Оригинал: {_escape(item.title)}", ""]
    if item.summary:
        lines += [_escape(item.summary), ""]
    rows = card_rows(item)
    if rows:
        lines += [f"- **{label}:** {_escape(value)}" for label, value in rows]
        lines.append("")
    if item.tags:
        tags = " · ".join(TAG_LABELS[tag] for tag in item.tags)
        lines += [f"**Признаки:** {tags}", ""]
    if item.why:
        lines += [f"**Почему важно:** {_escape(item.why)}", ""]
    if item.links:
        # Not clickable: a post may point at a working exploit.
        cited = ", ".join(f"`{defang(url)}`" for url in item.links)
        lines += [f"Ссылки из поста: {cited}", ""]
    if item.unsupported:
        removed = ", ".join(item.unsupported)
        lines += [f"*Нет в тексте статьи, убрано проверкой: {_escape(removed)}.*", ""]
    if item.duplicates:
        also = ", ".join(_link(dup.source_name, dup.url) for dup in item.duplicates)
        lines += [f"Также об этом: {also}", ""]
    return lines


def _front_matter(digest: DigestView) -> list[str]:
    """What a script needs without reading the text, as YAML front matter.
    JSON scalars are YAML, so every value is written as JSON."""
    stats = digest.stats
    fields = {
        "profile": digest.profile_name,
        "audience": digest.profile.audience,
        "period_start": digest.period_start.astimezone(MOSCOW).isoformat(timespec="minutes"),
        "period_end": digest.period_end.astimezone(MOSCOW).isoformat(timespec="minutes"),
        "built": (digest.finished_at or digest.created_at)
        .astimezone(MOSCOW)
        .isoformat(timespec="minutes"),
        "model": stats.get("llm"),
        "embeddings": stats.get("embedding_model"),
        "sources": stats.get("sources", 0),
        "publications": stats.get("window_total", 0),
        "candidates": stats.get("candidates", 0),
        "entries": stats.get("selected", 0),
    }
    lines = [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items()]
    return ["---", *lines, "---", ""]


# Contents are worth a line of their own from this many topics.
CONTENTS_FROM_TOPICS = 3
_ANCHOR_DROPS = re.compile(r"[^\w\- ]")


def anchor(heading: str) -> str:
    """The anchor GitLab and GitHub give a heading: lower case, punctuation
    dropped, spaces turned into hyphens."""
    return _ANCHOR_DROPS.sub("", heading.lower()).strip().replace(" ", "-")


def _contents(digest: DigestView) -> list[str]:
    if len(digest.topics) < CONTENTS_FROM_TOPICS:
        return []
    lines = ["## Содержание", ""]
    for number, topic in enumerate(digest.topics, start=1):
        heading = f"{number}. {topic.title}"
        lines.append(f"- [{_escape(heading)}](#{anchor(heading)}) · {len(topic.items)}")
    return [*lines, ""]


def _rejected(digest: DigestView) -> list[str]:
    """Every candidate left out, with its score and why: folded, as on the page."""
    if not digest.rejected:
        return []
    lines = [
        "<details>",
        f"<summary>Не вошло в выпуск: {len(digest.rejected)} кандидатов с оценкой и причиной"
        "</summary>",
        "",
    ]
    for item in digest.rejected:
        code = item.reject_reason or "low_score"
        reason = REJECT_REASONS.get(code, code)
        detail = f": {_escape(item.reason)}" if item.reason else ""
        lines.append(
            f"- {item.score:.2f} {_link(item.title, item.url)} "
            f"({_escape(item.source_name)}) - {reason}{detail}"
        )
    return [*lines, "", "</details>", ""]


def render_markdown(digest: DigestView) -> str:
    title = digest.title or f"Дайджест для профиля «{digest.profile_name}»"
    lines = [
        *_front_matter(digest),
        f"# {_escape(title)}",
        "",
        f"**Профиль:** {_escape(digest.profile_name)} (версия {digest.profile_version})  ",
        f"**Период:** {format_date(digest.period_start)} - {format_date(digest.period_end)}  ",
        f"**Сформирован:** {format_datetime(digest.finished_at or digest.created_at)} МСК",
        "",
    ]
    if digest.highlights:
        lines += ["## Главное", ""]
        lines += [f"- {_escape(highlight)}" for highlight in digest.highlights]
        lines.append("")
    lines += _contents(digest)
    if not digest.topics:
        lines += ["За выбранный период публикаций по интересам профиля не найдено.", ""]
    for number, topic in enumerate(digest.topics, start=1):
        lines += [f"## {number}. {_escape(topic.title)}", ""]
        if topic.overview:
            lines += [_escape(topic.overview), ""]
        for item in topic.items:
            lines += _item(item)
    lines += _rejected(digest)
    lines += ["---", "", "## Как составлен выпуск", ""]
    lines += [f"- {line}" for line in methodology(digest)]
    lines.append("")
    return "\n".join(lines)
