"""Render a digest as Markdown."""

from datetime import datetime
from zoneinfo import ZoneInfo

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


def _escape(text: str) -> str:
    """Keep article text from breaking out of Markdown link syntax."""
    return text.replace("[", "\\[").replace("]", "\\]").replace("\n", " ").strip()


def _link(text: str, url: str) -> str:
    return f"[{_escape(text)}]({url.replace(')', '%29').replace(' ', '%20')})"


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
    if stats.get("degraded"):
        lines.append(
            "Часть записей обработана резервным алгоритмом без языковой модели: "
            f"оценено моделью {stats.get('graded_by_model', 0)} из {stats.get('candidates', 0)}, "
            f"написано моделью {stats.get('written_by_model', 0)} из {stats.get('selected', 0)}."
        )
    return lines


def _item(item: ItemView) -> list[str]:
    meta = [item.source_name, format_date(item.published_at), f"релевантность {item.score:.2f}"]
    if item.interest_title:
        meta.append(f"интерес: {item.interest_title}")
    lines = [f"### {_link(item.headline, item.url)}", "", f"*{' · '.join(meta)}*", ""]
    if item.headline != item.title:
        lines += [f"Оригинал: {_escape(item.title)}", ""]
    if item.summary:
        lines += [item.summary, ""]
    if item.why:
        lines += [f"**Почему важно:** {item.why}", ""]
    if item.duplicates:
        also = ", ".join(_link(dup.source_name, dup.url) for dup in item.duplicates)
        lines += [f"Также об этом: {also}", ""]
    return lines


def render_markdown(digest: DigestView) -> str:
    title = digest.title or f"Дайджест для профиля «{digest.profile_name}»"
    lines = [
        f"# {title}",
        "",
        f"**Профиль:** {digest.profile_name} (версия {digest.profile_version})  ",
        f"**Период:** {format_date(digest.period_start)} - {format_date(digest.period_end)}  ",
        f"**Сформирован:** {format_datetime(digest.finished_at or digest.created_at)} МСК",
        "",
    ]
    if digest.highlights:
        lines += ["## Главное", ""]
        lines += [f"- {highlight}" for highlight in digest.highlights]
        lines.append("")
    if not digest.topics:
        lines += ["За выбранный период публикаций по интересам профиля не найдено.", ""]
    for number, topic in enumerate(digest.topics, start=1):
        lines += [f"## {number}. {topic.title}", ""]
        if topic.overview:
            lines += [topic.overview, ""]
        for item in topic.items:
            lines += _item(item)
    lines += ["---", "", "## Как составлен выпуск", ""]
    lines += [f"- {line}" for line in methodology(digest)]
    lines.append("")
    return "\n".join(lines)
