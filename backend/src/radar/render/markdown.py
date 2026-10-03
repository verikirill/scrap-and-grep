"""Render a digest as Markdown, the main format of a digest.

GitLab is the reference renderer: front matter for programs, anchors as
GitLab makes them for the table of contents, cards as tables and what was
left out in a folded block.
"""

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


def _cell(text: str) -> str:
    """Text of a table cell: a pipe would end the cell early."""
    return _escape(text).replace("|", "\\|")


def _yaml(value: object) -> str:
    """A front matter value. JSON is valid YAML, and its strings escape quotes,
    colons and line breaks a profile's name may have."""
    return json.dumps(value, ensure_ascii=False)


def front_matter(digest: DigestView) -> list[str]:
    """What a program reading the file needs before the text: who it is for,
    the period, the models and the funnel of publications."""
    stats = digest.stats
    made = (digest.finished_at or digest.created_at).astimezone(MOSCOW)
    fields: dict[str, object] = {
        "profile": digest.profile_name,
        "profile_version": digest.profile_version,
        "audience": digest.profile.audience,
        "period_start": digest.period_start.astimezone(MOSCOW).date().isoformat(),
        "period_end": digest.period_end.astimezone(MOSCOW).date().isoformat(),
        "generated": made.isoformat(timespec="minutes"),
        "llm": stats.get("llm", ""),
        "embedding": stats.get("embedding_model", ""),
        "sources": stats.get("sources", 0),
        "publications": stats.get("window_total", 0),
        "candidates": stats.get("candidates", 0),
        "entries": sum(len(topic.items) for topic in digest.topics),
    }
    return ["---", *(f"{key}: {_yaml(value)}" for key, value in fields.items()), "---", ""]


def gitlab_anchor(title: str, seen: dict[str, int]) -> str:
    """The id GitLab gives a heading: lower case, everything but letters,
    digits, underscores, hyphens and spaces dropped, each space to a hyphen,
    and -1, -2 for a heading seen before. `seen` holds the headings of the
    document so far, in order. Checked on git.codenrock.com: unlike its docs,
    GitLab keeps a run of hyphens, "новое - и" is "новое---и"."""
    anchor = re.sub(r"[^\w\- ]", "", title.strip().lower()).replace(" ", "-")
    count = seen.get(anchor)
    seen[anchor] = (count or 0) + 1
    return anchor if count is None else f"{anchor}-{count}"


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
        lines += ["| Поле | Значение |", "| --- | --- |"]
        lines += [f"| {_cell(label)} | {_cell(value)} |" for label, value in rows]
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


def _left_out(digest: DigestView) -> list[str]:
    """The candidates that did not make it, folded: open them to check the choice.
    The blank line after the summary makes GitLab read the list as Markdown."""
    if not digest.rejected:
        return []
    lines = [f"<details><summary>Не вошло в выпуск: {len(digest.rejected)}</summary>", ""]
    for item in digest.rejected:
        reason = REJECT_REASONS.get(item.reject_reason or "", item.reject_reason or "")
        parts = [
            _link(item.headline, item.url),
            _escape(item.source_name),
            f"оценка {item.score:.2f}",
        ]
        lines.append("- " + " · ".join([*parts, reason] if reason else parts))
    return [*lines, "", "</details>", ""]


def render_markdown(digest: DigestView) -> str:
    title = digest.title or f"Дайджест для профиля «{digest.profile_name}»"
    management = digest.profile.audience == "management"
    implications = management and bool(digest.implications)
    # A specialist's digest is long: sections first, so a reader jumps to one.
    contents = not management and bool(digest.topics)
    headings = [f"{number}. {topic.title}" for number, topic in enumerate(digest.topics, 1)]
    # Anchors as GitLab makes them, counting every heading before each section.
    seen: dict[str, int] = {}
    gitlab_anchor(title, seen)
    for fixed, present in (
        ("Содержание", contents),
        ("Что это значит для нас", implications),
        ("Главное", bool(digest.highlights)),
    ):
        if present:
            gitlab_anchor(fixed, seen)
    anchors = []
    for heading, topic in zip(headings, digest.topics, strict=True):
        anchors.append(gitlab_anchor(heading, seen))
        for item in topic.items:
            gitlab_anchor(item.headline, seen)

    lines = [
        *front_matter(digest),
        f"# {_escape(title)}",
        "",
        f"**Профиль:** {_escape(digest.profile_name)} (версия {digest.profile_version})  ",
        f"**Период:** {format_date(digest.period_start)} - {format_date(digest.period_end)}  ",
        f"**Сформирован:** {format_datetime(digest.finished_at or digest.created_at)} МСК",
        "",
    ]
    if contents:
        lines += ["## Содержание", ""]
        lines += [
            f"- [{_escape(heading)}](#{anchor})"
            for heading, anchor in zip(headings, anchors, strict=True)
        ]
        lines.append("")
    if implications:
        lines += ["## Что это значит для нас", ""]
        lines += [f"- {_escape(point)}" for point in digest.implications]
        lines.append("")
    if digest.highlights:
        lines += ["## Главное", ""]
        lines += [f"- {_escape(highlight)}" for highlight in digest.highlights]
        lines.append("")
    if not digest.topics:
        lines += ["За выбранный период публикаций по интересам профиля не найдено.", ""]
    for heading, topic in zip(headings, digest.topics, strict=True):
        lines += [f"## {_escape(heading)}", ""]
        if topic.overview:
            lines += [_escape(topic.overview), ""]
        for item in topic.items:
            lines += _item(item)
    lines += _left_out(digest)
    lines += ["---", "", "## Как составлен выпуск", ""]
    lines += [f"- {line}" for line in methodology(digest)]
    lines.append("")
    return "\n".join(lines)
