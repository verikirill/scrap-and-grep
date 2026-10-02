# /// script
# requires-python = ">=3.12"
# ///
"""The comparison of models as tables: the same week, profiles and dataset.

    uv run scripts/model_report.py examples/models

Reads the runs of backend/scripts/model_compare.py and backend/scripts/dataset_run.py
(<slug>.json and <slug>.dataset.json), moves each digest's Markdown into its
own file and prints the tables for examples/models/README.md.
"""

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

# In the order of the tables: the main model first, the offline mode last.
MODELS = {
    "gpt-oss-120b": ("`gpt-oss:120b`", "облако Ollama"),
    # The same model once more: how far two runs of one model drift apart.
    "gpt-oss-120b-repeat": ("`gpt-oss:120b`, повтор", "облако Ollama"),
    "gpt-oss-20b": ("`gpt-oss:20b`", "облако Ollama"),
    "gemma4-31b": ("`gemma4:31b`", "облако Ollama"),
    "nemotron-3-nano-30b": ("`nemotron-3-nano:30b`", "облако Ollama"),
    "qwen3.5-9b": ("`qwen3.5:9b`", "в стеке, видеокарта 8 ГБ"),
    "heuristic": ("без модели", "автономный режим"),
}
BASELINE = "gpt-oss-120b"
SLUGS = {
    "Специалист по ИБ АСУ ТП": "ics-security-engineer",
    "Руководство и сотрудники: кибербезопасность": "management-cybersecurity",
}


def dataset_scores() -> Any:
    path = Path(__file__).with_name("dataset_report.py")
    spec = importlib.util.spec_from_file_location("dataset_report", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.scores


def load(folder: Path, slug: str) -> dict[str, Any]:
    """The run, with each digest's Markdown moved out into a file of its own."""
    path = folder / f"{slug}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    moved = False
    for run in data["runs"]:
        if "markdown" in run:
            target = folder / slug / f"{SLUGS[run['profile']]}.md"
            target.parent.mkdir(exist_ok=True)
            target.write_text(run.pop("markdown"), encoding="utf-8", newline="\n")
            moved = True
    if moved:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
        )
    return data


def fallbacks(stats: dict[str, Any]) -> str:
    """Answers the offline mode gave instead of the model. None when the model
    answered all it was asked: a candidate an exclusion took out is not asked."""
    if not str(stats.get("llm", "")).startswith(("ollama", "openai")):
        return "модели нет"
    if not stats.get("degraded"):
        return "0"
    candidates, selected = stats.get("candidates") or 0, stats.get("selected") or 0
    grades = candidates - (stats.get("graded_by_model") or 0)
    texts = selected - (stats.get("written_by_model") or 0)
    parts = [f"{grades} оценок из {candidates}"] if grades else []
    parts += [f"{texts} текстов из {selected}"] if texts else []
    return ", ".join(parts) or "0"


def ids(run: dict[str, Any]) -> set[int]:
    return {item["article_id"] for item in run["items"]}


def specialist_row(name: str, place: str, run: dict[str, Any], base: dict[str, Any]) -> str:
    stats = run["stats"]
    kinds = stats.get("kinds", {})
    lookups = (stats.get("lookups_by_model") or 0, stats.get("lookups_by_pipeline") or 0)
    return (
        f"| {name} | {place} | {run['seconds']:.0f} | {fallbacks(stats)} "
        f"| {kinds.get('attack', 0)} / {kinds.get('vulnerability', 0)} / {kinds.get('news', 0)} "
        f"| {stats.get('priorities', {}).get('high', 0)} "
        f"| {len(ids(run) & ids(base))} из {len(ids(base))} "
        f"| {lookups[0]} / {lookups[1]} "
        f"| {stats.get('unsupported_fields', 0)} |"
    )


def management_row(name: str, run: dict[str, Any], base: dict[str, Any]) -> str:
    stats = run["stats"]
    tags = sum(len(item["tags"]) for item in run["items"])
    return (
        f"| {name} | {run['seconds']:.0f} | {fallbacks(stats)} "
        f"| {len(ids(run) & ids(base))} из {len(ids(base))} "
        f"| {tags / max(len(run['items']), 1):.1f} |"
    )


def dataset_row(name: str, score: dict[str, int]) -> str:
    return (
        f"| {name} | {score['read']} из {score['examples']} "
        f"| {score['kind']} из {score['graded']} | {score['priority']} из {score['graded']} "
        f"| {score['tags_found']} из {score['tags_wanted']} | {score['tags_extra']} |"
    )


def main() -> None:
    # A Windows console would print the tables in its own code page.
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "examples/models")
    scores = dataset_scores()
    runs = {slug: load(folder, slug) for slug in MODELS if (folder / f"{slug}.json").exists()}
    base = {run["profile"]: run for run in runs[BASELINE]["runs"]}
    ics, management = SLUGS

    print(
        "| Модель | Где работает | Сборка, с | Откаты на автономный режим "
        "| Атаки / уязвимости / прочее | Высокий приоритет "
        "| Совпало с `gpt-oss:120b` | Инструмент: модель / граф | Убрано проверкой |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    for slug, data in runs.items():
        run = next(r for r in data["runs"] if r["profile"] == ics)
        print(specialist_row(*MODELS[slug], run, base[ics]))

    print(
        "\n| Модель | Сборка, с | Откаты на автономный режим "
        "| Совпало с `gpt-oss:120b` | Признаков на запись |"
    )
    print("|---|---|---|---|---|")
    for slug, data in runs.items():
        run = next(r for r in data["runs"] if r["profile"] == management)
        print(management_row(MODELS[slug][0], run, base[management]))

    print(
        "\n| Модель | Прочитано страниц | Тип записи | Приоритет "
        "| Признаки руководства | Лишних признаков |"
    )
    print("|---|---|---|---|---|---|")
    for slug in runs:
        path = folder / f"{slug}.dataset.json"
        if path.exists():
            print(dataset_row(MODELS[slug][0], scores(json.loads(path.read_text("utf-8")))))


if __name__ == "__main__":
    main()
