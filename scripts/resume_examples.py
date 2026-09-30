# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""Run every sample resume through a running stack and save what it learned.

    uv run scripts/resume_examples.py                 # http://localhost:8080

For each file in examples/resumes a throwaway account is registered, the
resume is uploaded, and the recognised facts and the suggested profile are
written next to it as <name>.result.json. The account is deleted afterwards.
The result depends on the stack's mode: which parser (docling or built-in)
and which extractor (language model or the offline table) did the work is
recorded in the file.
"""

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
API = f"{BASE}/api/v1"
FOLDER = Path(__file__).resolve().parent.parent / "examples" / "resumes"
TIMEOUT_SECONDS = 240


def analyse(path: Path) -> dict[str, object]:
    password = f"examples-{uuid.uuid4().hex}"
    with httpx.Client(timeout=60) as client:
        client.post(
            f"{API}/auth/register",
            json={
                "email": f"examples.{uuid.uuid4().hex[:10]}@example.org",
                "password": password,
                "display_name": "Примеры",
            },
        ).raise_for_status()
        try:
            client.post(
                f"{API}/resume", content=path.read_bytes(), headers={"X-File-Name": path.name}
            ).raise_for_status()
            deadline = time.monotonic() + TIMEOUT_SECONDS
            resume = client.get(f"{API}/resume").json()
            while resume["status"] == "processing" and time.monotonic() < deadline:
                time.sleep(1)
                resume = client.get(f"{API}/resume").json()
            meta = client.get(f"{API}/meta").json()
        finally:
            client.post(f"{API}/auth/me/delete", json={"password": password})
    return {
        "file": path.name,
        "status": resume["status"],
        "error": resume["error"],
        "parser": resume["parser"],
        "llm": meta["llm_model"],
        "facts": resume["facts"],
        "suggestion": resume["suggestion"],
    }


def main() -> None:
    for path in sorted(FOLDER.iterdir()):
        if path.name.endswith(".result.json"):
            continue
        started = time.monotonic()
        result = analyse(path)
        target = path.with_name(f"{path.stem}.result.json")
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
        headline = (result["facts"] or {}).get("headline", result["error"])  # type: ignore[union-attr]
        print(f"{path.name}: {result['status']} in {time.monotonic() - started:.0f} s - {headline}")


if __name__ == "__main__":
    main()
