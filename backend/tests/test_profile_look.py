# ruff: noqa: F811  (the fixtures are imported from the accounts tests)
"""A profile's icon and colour: its owner's to pick, outside its versions."""

from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    api,
    client,
    database,
    profile_spec,
    register,
)


async def test_a_reader_picks_an_icon_and_a_colour_without_a_new_version(api: str) -> None:
    async with client(api) as guest, register(api, "lena") as lena, register(api, "max") as other:
        await guest.post("/auth/demo")
        examples = (await guest.get("/profiles")).json()
        await guest.patch(
            f"/profiles/{examples[-1]['id']}/look", json={"icon": "ai", "color": "pink"}
        )
        reordered = (await guest.get("/profiles")).json()
        profile = (await lena.post("/profiles", json=profile_spec())).json()
        picked = await lena.patch(
            f"/profiles/{profile['id']}/look", json={"icon": "factory", "color": "teal"}
        )
        refused = await lena.patch(
            f"/profiles/{profile['id']}/look", json={"icon": "<svg/onload=x>", "color": "teal"}
        )
        stranger = await other.patch(
            f"/profiles/{profile['id']}/look", json={"icon": "lock", "color": "red"}
        )
        after = (await lena.get(f"/profiles/{profile['id']}")).json()

    # A guest's example profiles come with their own look.
    assert {item["spec"]["name"]: item["icon"] for item in examples}["Специалист по ИБ АСУ ТП"] == (
        "shield"
    )
    # Copied in one transaction, the examples share a creation time; the list
    # must not reshuffle when one of them changes, or the page jumps to another.
    assert [item["id"] for item in reordered] == [item["id"] for item in examples]
    assert picked.status_code == 200
    assert (after["icon"], after["color"]) == ("factory", "teal")
    # The look is not the content: digests of this profile stay comparable.
    assert after["version"] == profile["version"]
    assert refused.status_code == 422
    assert stranger.status_code == 404
