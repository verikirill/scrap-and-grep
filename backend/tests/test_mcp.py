# ruff: noqa: F811  (the fixtures are imported from the accounts tests)
"""The MCP server over HTTP: a reader's key reaches that reader's news only."""

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    api,
    database,
    finished_digest,
    register,
    seed_articles,
)

MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


@asynccontextmanager
async def mcp_client() -> AsyncIterator[httpx.AsyncClient]:
    """The MCP endpoint as the api mounts it, with its session manager running
    (the in-process test client does not run the api's lifespan)."""
    from radar.mcp_server import server

    app, sessions = server.build()
    async with sessions.run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://radar.test") as client:
            yield client


async def call(
    client: httpx.AsyncClient, token: str | None, tool: str, **arguments: Any
) -> httpx.Response:
    headers = dict(MCP_HEADERS)
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    return await client.post("/", headers=headers, content=json.dumps(body))


def result(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "error" not in payload, payload
    return dict(payload["result"])


async def test_a_key_reaches_its_owners_digests_and_nobody_elses(api: str) -> None:
    async with register(api, "anna") as anna, register(api, "boris") as boris:
        ids = await seed_articles()
        digest_id = await finished_digest(anna, ids)
        anna_key = (await anna.post("/mcp/keys", json={"name": "Claude"})).json()
        boris_key = (await boris.post("/mcp/keys", json={"name": "Cursor"})).json()
        listed = (await anna.get("/mcp/keys")).json()

        async with mcp_client() as client:
            mine = result(await call(client, anna_key["token"], "my_digests"))
            text = result(await call(client, anna_key["token"], "read_digest", digest_id=digest_id))
            theirs = result(await call(client, boris_key["token"], "my_digests"))
            found = result(
                await call(client, anna_key["token"], "search_my_news", query="VPN шлюзы")
            )
            feed = result(await call(client, anna_key["token"], "my_feed", limit=5))
            stolen = await call(client, boris_key["token"], "read_digest", digest_id=digest_id)
            no_key = await call(client, None, "my_digests")
            wrong = await call(client, "tng_" + "x" * 43, "my_digests")
            used = (await anna.get("/mcp/keys")).json()
            assert (await anna.delete(f"/mcp/keys/{anna_key['id']}")).status_code == 204
            revoked = await call(client, anna_key["token"], "my_digests")

    assert anna_key["token"].startswith("tng_")
    # The key is shown once: the list has its first characters only.
    assert [key["prefix"] for key in listed] == [anna_key["token"][:10]]
    assert "token" not in listed[0]
    # A call marks the key as used, so the owner sees which keys are alive.
    assert listed[0]["last_used_at"] is None
    assert used[0]["last_used_at"] is not None
    assert [item["id"] for item in mine["structuredContent"]["digests"]] == [digest_id]
    assert "Уязвимость в VPN-шлюзах" in text["content"][0]["text"]
    assert theirs["structuredContent"]["digests"] == []
    titles = [item["title"] for item in found["structuredContent"]["items"]]
    assert titles
    assert all("VPN" in title for title in titles)
    assert feed["structuredContent"]["items"]
    assert all("reading_minutes" in item for item in feed["structuredContent"]["items"])
    stolen_payload = stolen.json()
    assert "error" in stolen_payload or stolen_payload["result"].get("isError")
    for refused in (no_key, wrong, revoked):
        assert refused.status_code == 401


async def test_a_reader_has_at_most_ten_keys(api: str) -> None:
    async with register(api, "vera") as vera:
        made = [await vera.post("/mcp/keys", json={"name": f"k{n}"}) for n in range(11)]
        other_id = uuid.uuid4()
        missing = await vera.delete(f"/mcp/keys/{other_id}")

    assert [response.status_code for response in made] == [201] * 10 + [409]
    assert missing.status_code == 404
