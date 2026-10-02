# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""Build the example digests that are committed under examples/.

    uv run scripts/make_examples.py [http://localhost:8080] [examples]

For every example profile it builds a weekly digest and saves it as Markdown,
DOCX and JSON. Then it shows how the selection follows the interests: the
ICS specialist's profile is edited three ways, one at a time, and for each
edit a second digest is built and every article that came or went is given
its reason, read from the digest's own record of what was graded and why.
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "examples")
API = f"{BASE}/api/v1"
# A fixed week, the one data/samples/articles.jsonl holds: the examples can be
# rebuilt from the snapshot on any machine, any day.
PERIOD = {"period_start": "2026-09-25T00:00:00+03:00", "period_end": "2026-10-02T16:00:00+03:00"}
BUILD_TIMEOUT_SECONDS = 1200

SLUGS = {
    "Специалист по ИБ АСУ ТП": "ics-security-engineer",
    "Руководитель ИТ-инфраструктуры": "it-infrastructure-lead",
    "Директор по цифровой трансформации": "digital-transformation-director",
    "Руководство и сотрудники: кибербезопасность": "management-cybersecurity",
}
CHANGED_PROFILE = "Специалист по ИБ АСУ ТП"

# Edits with a direct cause in the example week. An added interest is a weak
# demonstration here: the grader judges it against the whole reader, and a
# topic far from an ICS engineer scores low; a removed one is not.
REMOVED_INTEREST = "vulnerabilities"
NEW_EXCLUSION = "уязвимости продуктов Citrix"


def scenarios(spec: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """Three edits, each alone, so every change in the issue has one cause."""
    removed = next(item for item in spec["interests"] if item["id"] == REMOVED_INTEREST)
    return [
        (
            "01-removed-interest",
            f"Убран интерес «{removed['title']}»",
            {**spec, "interests": [i for i in spec["interests"] if i["id"] != REMOVED_INTEREST]},
        ),
        (
            "02-exclusion",
            f"Добавлено исключение «{NEW_EXCLUSION}»",
            {**spec, "exclusions": [*spec["exclusions"], NEW_EXCLUSION]},
        ),
        (
            "03-stricter",
            "Порог релевантности поднят с 0.50 до 0.70, размер выпуска снижен с 20 до 10",
            {**spec, "min_score": 0.7, "max_items": 10},
        ),
    ]


def slug(name: str) -> str:
    return SLUGS.get(name) or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "profile"


def build(client: httpx.Client, profile_id: str) -> dict[str, Any]:
    created = client.post(
        f"{API}/digests", json={"profile_id": profile_id, **PERIOD}
    ).raise_for_status().json()
    deadline = time.monotonic() + BUILD_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        digest = client.get(f"{API}/digests/{created['id']}").raise_for_status().json()
        if digest["status"] == "done":
            return dict(digest)
        if digest["status"] == "failed":
            raise SystemExit(f"digest failed: {digest['error']}")
        time.sleep(3)
    raise SystemExit("digest did not finish in time")


def export(client: httpx.Client, digest: dict[str, Any], stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    for extension in ("md", "docx"):
        body = client.get(f"{API}/digests/{digest['id']}/export.{extension}").raise_for_status()
        stem.with_suffix(f".{extension}").write_bytes(body.content)
    stats = digest["stats"]
    print(
        f"  {stem}: {stats['selected']} items, {len(digest['topics'])} topics, "
        f"{stats.get('duration_seconds')} s, llm={stats.get('llm')}",
        flush=True,
    )


def selected(digest: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {item["article_id"]: item for topic in digest["topics"] for item in topic["items"]}


def graded(digest: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Every candidate the digest graded and left out, with the reason."""
    return {item["article_id"]: item for item in digest["rejected"]}


def gone_because(item: dict[str, Any], after: dict[str, Any]) -> str:
    """Why an article of the first issue is not in the second one."""
    left_out = graded(after).get(item["article_id"])
    interests = {interest["id"] for interest in after["profile"]["interests"]}
    if left_out is None and item.get("interest_id") not in interests:
        return f"её интерес «{item['interest_title']}» убран из профиля"
    if left_out is None:
        return "в новом выпуске её нет даже среди кандидатов: поиск по новому профилю нашёл другие"
    reason = left_out.get("reject_reason")
    if reason == "excluded":
        return left_out["reason"].rstrip(".").lower()
    if reason == "low_score":
        threshold = after["profile"]["min_score"]
        return f"оценка {left_out['score']:.2f} ниже порога {threshold:.2f}"
    if reason == "over_limit":
        limit = after["profile"]["max_items"]
        return f"вытеснена: оценка {left_out['score']:.2f}, в выпуск вошли {limit} записей с оценкой выше"
    if reason == "duplicate":
        return "пересказ новости, уже вошедшей в выпуск"
    return reason or "не вошла"


def came_because(item: dict[str, Any], before: dict[str, Any]) -> str:
    """Why an article of the second issue was not in the first one."""
    known = {interest["title"] for interest in before["profile"]["interests"]}
    interest = item.get("interest_title") or "без интереса"
    new = "" if interest in known else " (новый)"
    earlier = graded(before).get(item["article_id"])
    was = ""
    if earlier is not None:
        was = f"; в прежнем выпуске: {gone_because(earlier | {'article_id': item['article_id']}, before)}"
    elif interest in known:
        was = "; в прежнем выпуске её не было среди кандидатов"
    return f"интерес «{interest}»{new}, оценка {item['score']:.2f}{was}"


def diff_markdown(
    title: str, before: dict[str, Any], after: dict[str, Any], spec: dict[str, Any]
) -> str:
    old, new = selected(before), selected(after)
    came = [item for article_id, item in new.items() if article_id not in old]
    went = [item for article_id, item in old.items() if article_id not in new]
    kept = [(old[article_id], item) for article_id, item in new.items() if article_id in old]

    def link(item: dict[str, Any]) -> str:
        return f"[{item['headline']}]({item['url']}) - {item['source_name']}"

    return "\n".join(
        [
            f"# {title}",
            "",
            f"Профиль: «{spec['name']}». Было {len(old)} публикаций, стало {len(new)}: "
            f"пришло {len(came)}, ушло {len(went)}, осталось {len(kept)}.",
            "",
            "Причины взяты из записи выпуска: у каждого кандидата сохранены оценка, интерес "
            "и причина, по которой он не вошёл.",
            "",
            *regraded_note(before["profile"], spec_after(after)),
            f"## Пришло ({len(came)})",
            "",
            *([f"- {link(item)}. {came_because(item, before)}." for item in came] or ["- нет"]),
            "",
            f"## Ушло ({len(went)})",
            "",
            *([f"- {link(item)}. {gone_because(item, after)}." for item in went] or ["- нет"]),
            "",
            f"## Осталось ({len(kept)})",
            "",
            *(
                [
                    f"- {link(item)}: {base['score']:.2f} → {item['score']:.2f}"
                    for base, item in kept
                ]
                or ["- нет"]
            ),
            "",
        ]
    )


def spec_after(digest: dict[str, Any]) -> dict[str, Any]:
    return dict(digest["profile"])


def regraded_note(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Interests and exclusions are the text the model grades against: an
    edit of them grades every candidate again, and a grade may move a little."""
    if before["interests"] == after["interests"] and before["exclusions"] == after["exclusions"]:
        return []
    return [
        "Правка интересов или исключений меняет текст профиля, по которому модель оценивает "
        "статьи, поэтому все кандидаты оценены заново. У статей, которых правка не касается, "
        "оценка может сдвинуться на несколько сотых, и статья у порога может уйти или прийти.",
        "",
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def main() -> None:
    with httpx.Client(timeout=60) as client:
        # A guest account starts with copies of the example profiles.
        client.post(f"{API}/auth/demo").raise_for_status()
        profiles = client.get(f"{API}/profiles").raise_for_status().json()
        digests = {}
        print("building one digest per profile", flush=True)
        for profile in profiles:
            digest = build(client, profile["id"])
            digests[profile["spec"]["name"]] = digest
            stem = OUT / slug(profile["spec"]["name"])
            export(client, digest, stem)
            write_json(OUT / "profiles" / f"{stem.name}.json", profile["spec"])

        print("editing the interests of the ICS specialist", flush=True)
        before = digests[CHANGED_PROFILE]
        spec = next(p["spec"] for p in profiles if p["spec"]["name"] == CHANGED_PROFILE)
        for folder, title, edited in scenarios(spec):
            temporary = client.post(
                f"{API}/profiles", json={**edited, "name": f"{spec['name']} ({folder})"}
            ).raise_for_status().json()
            try:
                after = build(client, temporary["id"])
                export(client, after, OUT / "change" / folder / "after")
                write_json(OUT / "change" / folder / "profile-after.json", edited)
                (OUT / "change" / folder / "diff.md").write_text(
                    diff_markdown(title, before, after, spec), encoding="utf-8", newline="\n"
                )
                print(f"  {folder}: done", flush=True)
            finally:
                client.delete(f"{API}/profiles/{temporary['id']}")


if __name__ == "__main__":
    main()
