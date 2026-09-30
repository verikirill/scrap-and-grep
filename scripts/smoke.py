# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""End-to-end check of a running stack, through the gateway.

    uv run scripts/smoke.py                 # http://localhost:8080
    uv run scripts/smoke.py http://host:port

It walks the path the jury will walk: sources and articles are there, a
profile selects something, a digest builds and reports progress, both exports
download, a short video is made when the server has the video profile on, and
editing the interests changes the selection. Then a new reader
registers, uploads a resume, gets a profile suggested from it and a personal
feed that reacts to a dislike, and deletes the account. Exit code 0 means every
step passed.

The digest part runs in a guest account ("try without registering"), so that
sign-in must be on (RADAR_DEMO_LOGIN=true, the default). The guest is deleted
at the end.
"""

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
API = f"{BASE}/api/v1"
BUILD_TIMEOUT_SECONDS = 600
RESUME_TIMEOUT_SECONDS = 180
SHORT_TIMEOUT_SECONDS = 900
RESUME = Path(__file__).resolve().parent.parent / "examples" / "resumes" / "ml-engineer.md"


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


def short_video(client: httpx.Client, digest_id: str) -> None:
    """Order the video, wait for it and check that an MP4 comes back."""
    started = time.monotonic()
    video = client.post(f"{API}/digests/{digest_id}/short").raise_for_status().json()
    stages: list[str] = []
    while video["status"] in ("queued", "running"):
        if time.monotonic() - started > SHORT_TIMEOUT_SECONDS:
            fail("the video was not ready in time")
        if video["stage"] and video["stage"] not in stages:
            stages.append(video["stage"])
        time.sleep(2)
        video = client.get(f"{API}/digests/{digest_id}/short").raise_for_status().json()
    if video["status"] != "done":
        fail(f"video failed: {video['error']}")
    mp4 = client.get(f"{BASE}{video['url']}").raise_for_status()
    if mp4.content[4:8] != b"ftyp":
        fail("the video is not an MP4")
    print(
        f"  stages seen: {' > '.join(stages)}; {video['duration_ms'] / 1000:.1f} s of video, "
        f"voice={video['voice']}, {len(mp4.content) / 1e6:.1f} MB "
        f"in {time.monotonic() - started:.0f} s"
    )


def selected_ids(digest: dict) -> set[int]:
    return {item["article_id"] for topic in digest["topics"] for item in topic["items"]}


def new_reader() -> None:
    """Registration, resume, a suggested profile, the feed, account removal."""
    with httpx.Client(timeout=30) as reader:
        step("a new reader registers")
        password = f"smoke-{uuid.uuid4().hex}"
        email = f"smoke.{uuid.uuid4().hex[:10]}@example.org"
        reader.post(
            f"{API}/auth/register",
            json={"email": email, "password": password, "display_name": "Smoke"},
        ).raise_for_status()
        if reader.get(f"{API}/auth/me").json()["email"] != email:
            fail("the new session is not recognised")

        step("the resume is read and a profile is suggested")
        reader.post(
            f"{API}/resume", content=RESUME.read_bytes(), headers={"X-File-Name": RESUME.name}
        ).raise_for_status()
        deadline = time.monotonic() + RESUME_TIMEOUT_SECONDS
        resume = reader.get(f"{API}/resume").json()
        while resume["status"] == "processing" and time.monotonic() < deadline:
            time.sleep(1)
            resume = reader.get(f"{API}/resume").json()
        if resume["status"] != "ready":
            fail(f"resume not processed: {resume['status']} {resume.get('error')}")
        facts, suggestion = resume["facts"], resume["suggestion"]
        print(f"  parser={resume['parser']}, headline '{facts['headline']}', {len(facts['skills'])} skills")
        print(f"  suggested topics: {'; '.join(item['title'] for item in suggestion['interests'])}")
        reader.post(f"{API}/profiles", json=suggestion).raise_for_status()

        step("the personal feed explains itself and learns from a dislike")
        feed = reader.get(f"{API}/feed", params={"limit": 10}).raise_for_status().json()["items"]
        ranked = [item for item in feed if not item["explore"]]
        if not ranked or not ranked[0]["reasons"]:
            fail("the feed has no ranked items with reasons")
        top = ranked[0]
        print(f"  top: '{top['title'][:70]}' - {'; '.join(r['text'] for r in top['reasons'])}")
        reader.post(
            f"{API}/feedback", json={"article_id": top["article_id"], "kind": "dislike"}
        ).raise_for_status()
        after = reader.get(f"{API}/feed", params={"limit": 60}).raise_for_status().json()["items"]
        if any(item["article_id"] == top["article_id"] for item in after):
            fail("a disliked article is still in the feed")

        step("the account is deleted with everything it owns")
        reader.post(f"{API}/auth/me/delete", json={"password": password}).raise_for_status()
        if reader.get(f"{API}/auth/me").json() is not None:
            fail("the session survived account deletion")


def main() -> None:
    with httpx.Client(timeout=30) as client:
        step("gateway and API are up")
        if client.get(f"{BASE}/healthz").status_code != 200:
            fail("gateway health check")
        ready = client.get(f"{BASE}/api/v1/meta").raise_for_status().json()
        print(f"  {ready['articles']} articles, embedding={ready['embedding_model']}, llm={ready['llm_model']}")
        if ready["articles"] == 0:
            fail("no articles: neither the sample snapshot nor the feeds were loaded")

        step("guest sign-in")
        guest = client.post(f"{API}/auth/demo").raise_for_status().json()
        if guest["is_admin"]:
            fail("a guest must not manage the source catalogue")

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

        if ready.get("shorts"):
            step("a short video of the digest")
            short_video(client, first["id"])

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
        client.post(f"{API}/auth/me/delete", json={"password": ""}).raise_for_status()

    new_reader()
    print("OK")


if __name__ == "__main__":
    main()
