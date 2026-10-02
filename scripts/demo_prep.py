# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""Prepare the account the demo is shown from (docs/DEMO.md, «Подготовка»).

    uv run scripts/demo_prep.py --email demo@tailgrep.local --password '...' --fresh

The account is registered if it does not exist and gets the four example
profiles. Then three weekly digests are built on the model the stack runs:

1. management, to open from the history during the demo;
2. the ICS specialist as it is: the issue the demo compares against;
3. the ICS specialist with the exclusion the demo adds by hand: built only to
   put the model's answers in the cache, then deleted.

During the demo the same exclusion is added in «Интересы», the issue builds
from the cache in seconds, and «Сравнение» opens on the two ICS issues.
Run it no earlier than an hour before the demo: the week moves on, and
publications that entered it since have not been graded yet.
"""

import argparse
import sys
import time
from typing import Any

import httpx

ICS = "Специалист по ИБ АСУ ТП"
MANAGEMENT = "Руководство и сотрудники: кибербезопасность"
EXCLUSION = "уязвимости продуктов Citrix"
BUILD_TIMEOUT_SECONDS = 900
# The API lets a reader create and delete ten digests a minute.
LIMITED_ATTEMPTS = 12


def options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8080")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Демо")
    parser.add_argument("--exclusion", default=EXCLUSION)
    parser.add_argument("--fresh", action="store_true", help="delete the account's digests first")
    return parser.parse_args()


def sign_in(client: httpx.Client, api: str, args: argparse.Namespace) -> None:
    credentials = {"email": args.email, "password": args.password}
    response = client.post(f"{api}/auth/login", json=credentials)
    if response.status_code == 401:
        response = client.post(
            f"{api}/auth/register", json={**credentials, "display_name": args.name}
        )
        if response.status_code == 409:
            raise SystemExit(f"{args.email} exists and the password does not fit")
        print(f"registered {args.email}")
    response.raise_for_status()


def limited(client: httpx.Client, method: str, url: str, **options: Any) -> httpx.Response:
    """A request under the API's rate limit: a 429 waits as long as it says."""
    for _ in range(LIMITED_ATTEMPTS):
        response = client.request(method, url, **options)
        if response.status_code != 429:
            return response.raise_for_status()
        time.sleep(float(response.headers.get("Retry-After", "10")))
    raise SystemExit(f"{method} {url}: still rate limited")


def add_examples(client: httpx.Client, api: str) -> dict[str, dict[str, Any]]:
    """The example profiles a guest starts with, copied into this account."""
    profiles = {p["spec"]["name"]: p for p in client.get(f"{api}/profiles").json()}
    with httpx.Client(timeout=60) as guest:
        guest.post(f"{api}/auth/demo").raise_for_status()
        try:
            for example in guest.get(f"{api}/profiles").raise_for_status().json():
                name = example["spec"]["name"]
                if name in profiles:
                    continue
                created = client.post(f"{api}/profiles", json=example["spec"])
                created.raise_for_status()
                look = {"icon": example["icon"], "color": example["color"]}
                client.patch(
                    f"{api}/profiles/{created.json()['id']}/look", json=look
                ).raise_for_status()
                profiles[name] = created.json()
                print(f"added profile {name}")
        finally:
            guest.post(f"{api}/auth/me/delete", json={"password": ""})
    return profiles


def save(client: httpx.Client, api: str, profile_id: str, spec: dict[str, Any]) -> None:
    client.put(f"{api}/profiles/{profile_id}", json=spec).raise_for_status()


def build(client: httpx.Client, api: str, profile_id: str, label: str) -> dict[str, Any]:
    started = time.monotonic()
    body = {"profile_id": profile_id, "period_days": 7}
    created = limited(client, "POST", f"{api}/digests", json=body)
    deadline = started + BUILD_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        digest = client.get(f"{api}/digests/{created.json()['id']}").raise_for_status().json()
        if digest["status"] == "done":
            stats = digest["stats"]
            print(
                f"{label}: {stats.get('selected')} entries, "
                f"{time.monotonic() - started:.0f} s, model {stats.get('llm')}",
                flush=True,
            )
            if stats.get("degraded"):
                print("  the model was unavailable for part of it: check the key and the model")
            return dict(digest)
        if digest["status"] == "failed":
            raise SystemExit(f"{label} failed: {digest['error']}")
        time.sleep(3)
    raise SystemExit(f"{label} did not finish in {BUILD_TIMEOUT_SECONDS} s")


def main() -> None:
    args = options()
    api = f"{args.base.rstrip('/')}/api/v1"
    with httpx.Client(timeout=60) as client:
        sign_in(client, api, args)
        if args.fresh:
            listed = client.get(f"{api}/digests", params={"limit": 100}).raise_for_status()
            for digest in listed.json():
                limited(client, "DELETE", f"{api}/digests/{digest['id']}")
        profiles = add_examples(client, api)
        if missing := {ICS, MANAGEMENT} - profiles.keys():
            raise SystemExit(f"no example profile {', '.join(sorted(missing))} on this stack")
        ics = profiles[ICS]
        spec = {
            **ics["spec"],
            "exclusions": [e for e in ics["spec"]["exclusions"] if e != args.exclusion],
        }
        save(client, api, ics["id"], spec)

        build(client, api, profiles[MANAGEMENT]["id"], "management")
        before = build(client, api, ics["id"], "ICS as it is")

        save(client, api, ics["id"], {**spec, "exclusions": [*spec["exclusions"], args.exclusion]})
        after = None
        try:
            after = build(client, api, ics["id"], "ICS with the exclusion (for the cache)")
            change = (
                client.get(
                    f"{api}/digests/compare", params={"base": before["id"], "other": after["id"]}
                )
                .raise_for_status()
                .json()
            )
        finally:
            # The demo starts from the profile as it is and its issue as the latest.
            save(client, api, ics["id"], spec)
            if after is not None:
                limited(client, "DELETE", f"{api}/digests/{after['id']}")

    print(f"\nIn the demo add the exclusion «{args.exclusion}» to «{ICS}».")
    print(f"The issue will lose {len(change['removed'])} and gain {len(change['added'])}:")
    for item in change["removed"]:
        print(f"  - {item['headline']}")
    for item in change["added"]:
        print(f"  + {item['headline']}")
    if not change["removed"]:
        print("Nothing leaves: pick an exclusion that matches this week's issue (--exclusion).")
        sys.exit(1)


if __name__ == "__main__":
    main()
