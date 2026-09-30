# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""End-to-end check of a running stack, through the gateway.

    uv run scripts/smoke.py                 # http://localhost:8080
    uv run scripts/smoke.py http://host:port

It walks the path the jury will walk: sources and articles are there, a
profile selects something, a digest builds and reports progress, both exports
download, and editing the interests changes the selection. Exit code 0 means
every step passed.
"""

import json
import sys
import time

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
API = f"{BASE}/api/v1"
BUILD_TIMEOUT_SECONDS = 600


def step(name: str) -> None:
    print(f"- {name}", flush=True)


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def wait_for_digest(client: httpx.Client, digest_id: str) -> dict:
    """Follow the SSE stream until the build ends, then return the digest."""
    stages: list[str] = []
    deadline = time.monotonic() + BUILD_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        with client.stream("GET", f"{API}/digests/{digest_id}/events", timeout=None) as stream:
            for line in stream.iter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:])
                stage = event.get("stage")
                if stage and stage not in stages:
                    stages.append(stage)
                if event.get("status") == "failed":
                    fail(f"digest failed: {event.get('error')}")
                if event.get("status") == "done":
                    print(f"  stages seen: {' > '.join(stages)}")
                    return client.get(f"{API}/digests/{digest_id}").raise_for_status().json()
    fail("digest did not finish in time")
    raise AssertionError  # unreachable


def selected_ids(digest: dict) -> set[int]:
    return {item["article_id"] for topic in digest["topics"] for item in topic["items"]}


def main() -> None:
    with httpx.Client(timeout=30) as client:
        step("gateway and API are up")
        if client.get(f"{BASE}/healthz").status_code != 200:
            fail("gateway health check")
        ready = client.get(f"{BASE}/api/v1/meta").raise_for_status().json()
        print(f"  {ready['articles']} articles, embedding={ready['embedding_model']}, llm={ready['llm_model']}")
        if ready["articles"] == 0:
            fail("no articles: neither the sample snapshot nor the feeds were loaded")

        step("sources and full-text search")
        sources = client.get(f"{API}/sources").raise_for_status().json()
        found = client.get(f"{API}/articles", params={"q": "уязвимость", "limit": 5}).raise_for_status().json()
        print(f"  {len(sources)} sources, {found['total']} articles match 'уязвимость'")
        if not sources or found["total"] == 0:
            fail("catalog is empty")

        step("profile preview")
        profile = client.get(f"{API}/profiles").raise_for_status().json()[0]
        preview = client.post(
            f"{API}/selection/preview", json={"profile": profile["spec"], "period_days": 7}
        ).raise_for_status().json()
        print(f"  '{profile['spec']['name']}': {preview['selected']} of {preview['candidates']} candidates")

        step("build a digest and follow its progress")
        created = client.post(
            f"{API}/digests", json={"profile_id": profile["id"], "period_days": 7}
        ).raise_for_status().json()
        first = wait_for_digest(client, created["id"])
        stats = first["stats"]
        print(f"  '{first['title']}': {stats['selected']} items in {len(first['topics'])} topics, {stats.get('duration_seconds')} s")
        if stats["selected"] == 0:
            fail("digest is empty")
        if any(not item["url"].startswith("http") for t in first["topics"] for item in t["items"]):
            fail("an item lost its source link")

        step("exports")
        markdown = client.get(f"{API}/digests/{first['id']}/export.md").raise_for_status()
        docx = client.get(f"{API}/digests/{first['id']}/export.docx").raise_for_status()
        print(f"  markdown {len(markdown.content)} bytes, docx {len(docx.content)} bytes")
        if not markdown.text.startswith("# ") or docx.content[:2] != b"PK":
            fail("export format")

        step("changing interests changes the selection")
        spec = profile["spec"]
        narrowed = {**spec, "name": "smoke-test profile", "interests": spec["interests"][:1]}
        temporary = client.post(f"{API}/profiles", json=narrowed).raise_for_status().json()
        try:
            created = client.post(
                f"{API}/digests", json={"profile_id": temporary["id"], "period_days": 7}
            ).raise_for_status().json()
            second = wait_for_digest(client, created["id"])
            diff = client.get(
                f"{API}/digests/compare", params={"base": first["id"], "other": second["id"]}
            ).raise_for_status().json()
            print(
                f"  added {len(diff['added'])}, removed {len(diff['removed'])}, kept {len(diff['kept'])}; "
                f"interests removed: {sum(1 for c in diff['interest_changes'] if c['change'] == 'removed')}"
            )
            if selected_ids(first) == selected_ids(second):
                fail("selection did not change after the interests changed")
            client.delete(f"{API}/digests/{second['id']}")
        finally:
            client.delete(f"{API}/profiles/{temporary['id']}")
            client.delete(f"{API}/digests/{first['id']}")

    print("OK")


if __name__ == "__main__":
    main()
