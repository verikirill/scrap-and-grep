# ruff: noqa: F811  (the fixtures are imported from the accounts tests)
"""The first-run introduction: offered once to a new reader, on any browser."""

from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    PASSWORD,
    api,
    client,
    database,
    register,
)


async def test_a_new_reader_is_introduced_once_whichever_browser_they_use(api: str) -> None:
    async with register(api, "vera") as vera:
        before = (await vera.get("/auth/me")).json()
        finished = await vera.post("/auth/me/onboarded")
        again = await vera.post("/auth/me/onboarded")
        after = (await vera.get("/auth/me")).json()

    # Signing in elsewhere: the mark is kept with the account, not the browser.
    async with client(api) as elsewhere:
        await elsewhere.post("/auth/login", json={"email": before["email"], "password": PASSWORD})
        there = (await elsewhere.get("/auth/me")).json()

    assert before["onboarded_at"] is None
    assert finished.status_code == 200
    assert after["onboarded_at"] is not None
    # A second finish (the introduction taken again on demand) keeps the first time.
    assert again.json()["onboarded_at"] == finished.json()["onboarded_at"]
    assert there["onboarded_at"] == after["onboarded_at"]


async def test_only_a_signed_in_reader_can_finish_it_or_read_the_templates(api: str) -> None:
    async with client(api) as visitor:
        finish = await visitor.post("/auth/me/onboarded")
        templates = await visitor.get("/profile-templates")

    assert finish.status_code == 401
    assert templates.status_code == 401


async def test_a_template_becomes_the_readers_first_profile(api: str) -> None:
    async with register(api, "gleb") as gleb:
        templates = (await gleb.get("/profile-templates")).json()
        created = await gleb.post("/profiles", json=templates[0]["spec"])
        me = (await gleb.get("/auth/me")).json()

    assert len(templates) >= 2
    assert all(template["spec"]["interests"] for template in templates)
    assert templates[0]["icon"]
    assert templates[0]["color"]
    assert created.status_code == 201
    assert created.json()["spec"]["name"] == templates[0]["spec"]["name"]
    assert me["profiles"] == 1
