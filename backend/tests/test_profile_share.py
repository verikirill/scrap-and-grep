# ruff: noqa: F811  (the fixtures are imported from the accounts tests)
"""A profile handed over by link: a copy for whoever accepts, until the owner closes it."""

from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    api,
    client,
    database,
    profile_spec,
    register,
)


async def test_a_link_hands_a_copy_to_another_reader_until_the_owner_closes_it(
    api: str,
) -> None:
    async with register(api, "lena") as lena, register(api, "max") as max_, client(api) as nobody:
        profile = (await lena.post("/profiles", json=profile_spec("АСУ ТП"))).json()
        await lena.patch(
            f"/profiles/{profile['id']}/look", json={"icon": "factory", "color": "#1E9C8A"}
        )
        first = (await lena.post(f"/profiles/{profile['id']}/share")).json()
        again = (await lena.post(f"/profiles/{profile['id']}/share")).json()
        token = first["share_token"]
        not_theirs = await max_.post(f"/profiles/{profile['id']}/share")
        anonymous = await nobody.get(f"/shared-profiles/{token}")

        seen = (await max_.get(f"/shared-profiles/{token}")).json()
        added = await max_.post(f"/shared-profiles/{token}/accept")
        seen_after = (await max_.get(f"/shared-profiles/{token}")).json()
        twice = await max_.post(f"/shared-profiles/{token}/accept")
        owner_view = (await lena.get(f"/shared-profiles/{token}")).json()

        await lena.delete(f"/profiles/{profile['id']}/share")
        closed = await max_.get(f"/shared-profiles/{token}")
        max_profiles = (await max_.get("/profiles")).json()

    # One link per profile: a second click must not break the one already sent.
    assert token
    assert again["share_token"] == token
    assert not_theirs.status_code == 404
    assert anonymous.status_code == 401
    assert seen["spec"]["name"] == "АСУ ТП"
    assert seen["own_id"] is None
    # The copy is the recipient's own: their id, the same look, a first version, no link.
    assert added.status_code == 201
    copy = added.json()
    assert copy["id"] != profile["id"]
    assert copy["version"] == 1
    assert (copy["icon"], copy["color"], copy["share_token"]) == ("factory", "#1e9c8a", None)
    assert seen_after["own_id"] == copy["id"]
    assert twice.status_code == 200
    assert twice.json()["id"] == copy["id"]
    assert owner_view["own_id"] == profile["id"]
    # A closed link is gone, the copy made through it stays.
    assert closed.status_code == 404
    assert [item["id"] for item in max_profiles] == [copy["id"]]


async def test_a_colour_of_ones_own_is_a_hex_value_and_nothing_else(api: str) -> None:
    async with register(api, "lena") as lena:
        profile = (await lena.post("/profiles", json=profile_spec())).json()
        look = f"/profiles/{profile['id']}/look"
        refused = [
            (await lena.patch(look, json={"icon": "lock", "color": color})).status_code
            for color in ("#12abeg", "#12ab", "red;background:url(x)", "#12abef00")
        ]
        junk_link = await lena.get("/shared-profiles/..%2F..%2Fprofiles")

    assert refused == [422, 422, 422, 422]
    assert junk_link.status_code in (404, 422)


def test_the_access_log_does_not_keep_share_links() -> None:
    import logging

    from radar.logging import configure_logging

    configure_logging("INFO", json=True)
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("10.0.0.1:5000", "GET", "/api/v1/shared-profiles/Abc_def-123456789012/accept", "1.1", 200),
        None,
    )
    for keep in logging.getLogger("uvicorn.access").filters:
        keep.filter(record)

    assert "Abc_def" not in record.getMessage()
    assert "/api/v1/shared-profiles/" in record.getMessage()
