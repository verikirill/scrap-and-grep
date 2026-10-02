# /// script
# requires-python = ">=3.12"
# ///
"""The dataset run as a page: what the organizers want next to what came out.

uv run scripts/dataset_report.py examples/dataset/run.json examples/dataset/README.md
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

KINDS = {"Атака": "attack", "Уязвимость": "vulnerability", "Инфо": "news"}
KIND_WORDS = {"attack": "атака", "vulnerability": "уязвимость", "news": "новость"}
PRIORITIES = {"Высокий": "высокий", "Средний": "средний", "Низкий": "низкий"}
# The dataset's management tags by number, as the run names them.
TAGS = {
    "1": "ru",
    "2": "abroad",
    "3": "financial_loss",
    "4": "critical_infrastructure",
    "5": "energy",
    "6": "industry",
    "7": "reputation",
    "8": "data_leak",
    "9": "government_law",
    "10": "mass_service",
    "11": "people_events",
    "12": "curious",
}


def wanted_tags(grouping: str) -> set[str]:
    return {
        TAGS[number]
        for number in re.findall(r"(?m)^\s*(\d+)\.", grouping)
        if number in TAGS
    }


def cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "/")


def specialist_block(result: dict[str, Any]) -> list[str]:
    example = result["example"]
    lines = [
        f"### {example['id']}: {cell(example['title'])}",
        "",
        f"Источник: {', '.join(example['urls'])}",
        "",
    ]
    if "kind" not in result:
        reason = result.get("failed") or "; ".join(
            p["error"] for p in result["pages"] if p["error"]
        )
        return [*lines, f"Не прочитано: {reason}.", ""]
    ours_kind = KIND_WORDS[result["kind"]]
    lines += [
        "| | Датасет | Tail&Grep |",
        "|---|---|---|",
        f"| Группа | {example['grouping']} | {ours_kind} |",
        (
            f"| Приоритет | {example['priority']} | {result['priority'] or '-'}"
            f"{f' ({result[chr(112) + 'riority_reason']})' if result['priority_reason'] else ''} |"
        ),
        "",
        "**Желаемый вывод датасета**",
        "",
        *[
            f"> {line}" if line.strip() else ">"
            for line in example["wanted"].splitlines()
        ],
        "",
        f"**Tail&Grep:** {result['headline']}",
        "",
        result["summary"],
        "",
        *[f"- **{field['label']}:** {field['value']}" for field in result["fields"]],
    ]
    if result["links"]:
        lines.append(
            f"- **Ссылки из поста:** {', '.join(f'`{link}`' for link in result['links'])}"
        )
    if result["unsupported"]:
        lines.append(
            f"- *Нет в тексте, убрано проверкой:* {', '.join(result['unsupported'])}"
        )
    return [*lines, ""]


def management_block(result: dict[str, Any]) -> list[str]:
    example = result["example"]
    lines = [f"### {example['id']}", "", f"Источник: {', '.join(example['urls'])}", ""]
    if "kind" not in result:
        reason = result.get("failed") or "; ".join(
            p["error"] for p in result["pages"] if p["error"]
        )
        return [*lines, f"Не прочитано: {reason}.", ""]
    wanted = wanted_tags(example["grouping"])
    ours = set(result["tag_ids"])
    lines += [
        (
            f"Признаки: совпало {len(wanted & ours)} из {len(wanted)} в датасете, "
            f"у нас лишних {len(ours - wanted)}."
        ),
        "",
        "**Желаемый вывод датасета**",
        "",
        *[
            f"> {line}" if line.strip() else ">"
            for line in example["wanted"].splitlines()
        ],
        "",
        f"**Tail&Grep:** {result['headline']}",
        "",
        result["summary"],
        "",
        f"Признаки: {' · '.join(result['tags'])}",
        "",
    ]
    return lines


def scores(results: list[dict[str, Any]]) -> dict[str, int]:
    """How a run agrees with the dataset: pages read, the kind and priority of
    the specialists' attacks and vulnerabilities, the management tags found."""
    graded = [
        r
        for r in results
        if r["example"]["audience"] == "specialist"
        and "kind" in r
        and r["example"]["grouping"].strip() != "Инфо"
    ]
    management = [r for r in results if r["example"]["audience"] == "management" and "kind" in r]
    return {
        "read": sum("kind" in r for r in results),
        "examples": len(results),
        "graded": len(graded),
        "kind": sum(KINDS.get(r["example"]["grouping"].strip()) == r["kind"] for r in graded),
        "priority": sum(
            PRIORITIES.get(r["example"]["priority"].strip()) == r["priority"] for r in graded
        ),
        "tags_wanted": sum(len(wanted_tags(r["example"]["grouping"])) for r in management),
        "tags_found": sum(
            len(wanted_tags(r["example"]["grouping"]) & set(r["tag_ids"])) for r in management
        ),
        "tags_extra": sum(
            len(set(r["tag_ids"]) - wanted_tags(r["example"]["grouping"])) for r in management
        ),
    }


def main() -> None:
    run, out = (Path(arg) for arg in sys.argv[1:3])
    results = json.loads(run.read_text(encoding="utf-8"))
    specialists = [r for r in results if r["example"]["audience"] == "specialist"]
    management = [r for r in results if r["example"]["audience"] == "management"]
    score = scores(results)
    text = [
        "# Прогон по датасету организаторов",
        "",
        (
            "Каждый из 21 примера датасета ([docs/task](../../docs/task/TASK.md)) прогнан "
            "через те же шаги, что и запись выпуска: страница читается так же, как источник, "
            "модель (`gpt-oss:120b`) ставит оценку и тип записи и пишет карточку или сводку для "
            "аудитории примера, номера уязвимостей сверяются с CISA KEV и БДУ, карточка "
            "проверяется по тексту. Рядом стоит «желаемый вывод» из датасета. Скрипты: "
            "`scripts/dataset_json.py`, `backend/scripts/dataset_run.py`, "
            "`scripts/dataset_report.py`; сырые ответы в [run.json](run.json)."
        ),
        "",
        "## Итог",
        "",
        f"- Прочитано страниц: {score['read']} из {score['examples']}. Не прочитано: "
        + (
            "; ".join(
                f"{r['example']['id']} ({'; '.join(p['error'] for p in r['pages'] if p['error'])})"
                for r in results
                if "kind" not in r and "pages" in r
            )
            or "нет"
        )
        + ".",
        (
            f"- Специалисты, атаки и уязвимости: тип совпал в {score['kind']} "
            f"из {score['graded']}, приоритет в {score['priority']} из {score['graded']}."
        ),
        (
            "- Специалисты, посты Telegram: датасет кладёт их в группу «Инфо» по источнику, "
            "Tail&Grep определяет тип по содержанию, поэтому пост об уязвимости получает "
            "карточку уязвимости и ссылки из поста, как в желаемом выводе."
        ),
        (
            f"- Руководство: признаков датасета найдено {score['tags_found']} "
            f"из {score['tags_wanted']}, лишних поставлено {score['tags_extra']}."
        ),
        "",
        (
            "Где Tail&Grep расходится с датасетом и почему, видно в разборе ниже. Два "
            "расхождения - ошибки самого датасета, а не модели: у specialist-4 (Axios) в "
            "датасете указан CVE-2025-59287, это уязвимость WSUS из specialist-7; у specialist-3 "
            "страной жертвы назван РФ при атаке на Европу и Юго-Восточную Азию. У specialist-7 "
            "датасет пишет «эксплойта нет», а CVE-2025-59287 с 24 октября 2025 года в каталоге "
            "CISA KEV: приоритет у нас выше по правилу самого датасета. У specialist-4 датасет "
            "пишет «публичный эксплойт», а на странице dbugs, по которой собран пример, после "
            "заголовка «Exploit» нет текста: признак, видимо, показан значком. Модель его не "
            "видит, и запись получает средний приоритет."
        ),
        "",
        "## Специалистам",
        "",
    ]
    for result in specialists:
        text += specialist_block(result)
    text += ["## Руководству", ""]
    for result in management:
        text += management_block(result)
    out.write_text("\n".join(text), encoding="utf-8", newline="\n")
    print(f"{len(results)} examples written to {out}")


if __name__ == "__main__":
    main()
