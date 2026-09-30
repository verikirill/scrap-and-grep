# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""Build the example digests that are committed under examples/.

    uv run scripts/make_examples.py [http://localhost:8080] [examples]

For every stored profile it builds a weekly digest and saves it as Markdown
and DOCX. Then it shows the effect of editing interests: the first profile is
copied, one interest is replaced with another, a second digest is built and the
difference between the two issues is written to change/diff.md.
"""

import json
import re
import sys
import time
from pathlib import Path

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "examples")
API = f"{BASE}/api/v1"
PERIOD_DAYS = 7
BUILD_TIMEOUT_SECONDS = 1200

REPLACEMENT_INTEREST = {
    "id": "security-products",
    "title": "Отечественные средства защиты информации",
    "description": (
        "Новые версии и сертификация российских средств защиты: межсетевые экраны, "
        "SIEM, EDR, средства защиты АСУ ТП."
    ),
    "keywords": ["сертификат ФСТЭК", "межсетевой экран", "SIEM", "EDR", "NGFW", "импортозамещение"],
    "weight": 1.2,
}

SLUGS = {
    "Специалист по ИБ АСУ ТП": "ics-security-engineer",
    "Руководитель ИТ-инфраструктуры": "it-infrastructure-lead",
    "Директор по цифровой трансформации": "digital-transformation-director",
}


def slug(name: str) -> str:
    return SLUGS.get(name) or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "profile"


def build(client: httpx.Client, profile_id: str) -> dict:
    created = client.post(
        f"{API}/digests", json={"profile_id": profile_id, "period_days": PERIOD_DAYS}
    ).raise_for_status().json()
    deadline = time.monotonic() + BUILD_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        digest = client.get(f"{API}/digests/{created['id']}").raise_for_status().json()
        if digest["status"] == "done":
            return digest
        if digest["status"] == "failed":
            raise SystemExit(f"digest failed: {digest['error']}")
        time.sleep(3)
    raise SystemExit("digest did not finish in time")


def export(client: httpx.Client, digest: dict, stem: Path) -> None:
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


def diff_markdown(before: dict, after: dict, diff: dict) -> str:
    def rows(items: list[dict]) -> list[str]:
        return [
            f"- [{item['headline']}]({item['url']}) - {item['source_name']}, "
            f"оценка {item['score']:.2f}"
            for item in items
        ] or ["- нет"]

    changes = {"added": "добавлен", "removed": "убран", "changed": "изменён"}
    interest_lines = [
        f"- {change['title']}: {changes[change['change']]}" for change in diff["interest_changes"]
    ]
    kept = [
        f"- [{entry['item']['headline']}]({entry['item']['url']}) - "
        f"{entry['base_score']:.2f} → {entry['item']['score']:.2f}"
        for entry in diff["kept"]
    ] or ["- нет"]
    return "\n".join(
        [
            "# Как изменилась подборка после правки интересов",
            "",
            f"Было: «{before['title']}», {before['stats']['selected']} публикаций.  ",
            f"Стало: «{after['title']}», {after['stats']['selected']} публикаций.",
            "",
            "## Что изменили в профиле",
            "",
            *interest_lines,
            "",
            f"## Появилось ({len(diff['added'])})",
            "",
            *rows(diff["added"]),
            "",
            f"## Ушло ({len(diff['removed'])})",
            "",
            *rows(diff["removed"]),
            "",
            f"## Осталось ({len(diff['kept'])})",
            "",
            *kept,
            "",
        ]
    )


def main() -> None:
    with httpx.Client(timeout=60) as client:
        profiles = client.get(f"{API}/profiles").raise_for_status().json()
        digests = {}
        print("building one digest per profile", flush=True)
        for profile in profiles:
            digest = build(client, profile["id"])
            digests[profile["id"]] = digest
            export(client, digest, OUT / slug(profile["spec"]["name"]))

        print("editing interests of the first profile", flush=True)
        original = profiles[0]
        spec = original["spec"]
        edited = {
            **spec,
            "name": f"{spec['name']} (после правки)",
            "interests": [*spec["interests"][:-1], REPLACEMENT_INTEREST],
        }
        temporary = client.post(f"{API}/profiles", json=edited).raise_for_status().json()
        try:
            before = digests[original["id"]]
            after = build(client, temporary["id"])
            export(client, before, OUT / "change" / "before")
            export(client, after, OUT / "change" / "after")
            diff = client.get(
                f"{API}/digests/compare", params={"base": before["id"], "other": after["id"]}
            ).raise_for_status().json()
            (OUT / "change" / "diff.md").write_text(
                diff_markdown(before, after, diff), encoding="utf-8", newline="\n"
            )
            (OUT / "change" / "profile-before.json").write_text(
                json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
            )
            (OUT / "change" / "profile-after.json").write_text(
                json.dumps(edited, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
            )
            print(
                f"  change: +{len(diff['added'])} -{len(diff['removed'])} ={len(diff['kept'])}",
                flush=True,
            )
        finally:
            client.delete(f"{API}/profiles/{temporary['id']}")


if __name__ == "__main__":
    main()
