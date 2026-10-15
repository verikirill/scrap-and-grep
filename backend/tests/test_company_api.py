# ruff: noqa: F811  (the fixtures are imported from the accounts tests)
"""A company space through the HTTP API: teams, accounts made for their
people, invitations, and who can reach what."""

from typing import Any

import httpx

from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    PASSWORD,
    api,
    client,
    database,
    register,
)

SOC = {
    "name": "SOC",
    "services": "Круглосуточный мониторинг в MaxPatrol SIEM, реагирование на инциденты.",
    "systems": ["MaxPatrol SIEM"],
}
NETWORK = {
    "name": "Сети",
    "services": "Маршрутизаторы, межсетевые экраны и VPN между площадками.",
    "systems": ["Cisco ASA"],
}


async def make_team(manager: httpx.AsyncClient, team: dict[str, Any] = SOC) -> dict[str, Any]:
    draft = await manager.post("/company/teams/draft", json=team)
    assert draft.status_code == 200, draft.text
    created = await manager.post("/company/teams", json={**team, "spec": draft.json()["spec"]})
    assert created.status_code == 201, created.text
    return created.json()


async def add(manager: httpx.AsyncClient, team_id: str, *people: dict[str, str]) -> Any:
    response = await manager.post(f"/company/teams/{team_id}/members", json={"people": people})
    assert response.status_code == 201, response.text
    return response.json()


def token_of(member: dict[str, Any]) -> str:
    return str(member["invite_path"]).removeprefix("/invite/")


async def test_a_person_from_the_list_comes_in_with_a_ready_profile(api: str) -> None:
    async with register(api, "boss") as boss:
        before = await boss.get("/company")
        made = await boss.post("/company", json={"name": "Энергосеть", "about": "Сетевая компания"})
        team = await make_team(boss)
        added = await add(
            boss,
            team["id"],
            {"name": "Анна Смирнова", "email": "Anna@Energo.example", "job_title": "Инженер SOC"},
            {"name": "Олег", "email": "oleg@energo.example", "job_title": "Начальник SOC"},
        )
        company = (await boss.get("/company")).json()
        boss_me = (await boss.get("/auth/me")).json()

    anna = next(m for m in added["created"] if m["email"] == "anna@energo.example")
    async with client(api) as visitor:
        invite = await visitor.get(f"/auth/invite/{token_of(anna)}")
        accepted = await visitor.post(f"/auth/invite/{token_of(anna)}", json={"password": PASSWORD})
        me = (await visitor.get("/auth/me")).json()
        profiles = (await visitor.get("/profiles")).json()
        again = await visitor.get(f"/auth/invite/{token_of(anna)}")
    async with client(api) as elsewhere:
        login = await elsewhere.post(
            "/auth/login", json={"email": "anna@energo.example", "password": PASSWORD}
        )

    assert before.json() is None
    assert made.status_code == 201
    assert boss_me["company"] == {
        "company": "Энергосеть",
        "team": None,
        "role": "owner",
        "job_title": None,
        "manager": None,
    }
    assert team["spec"]["systems"][0] == "MaxPatrol SIEM"
    assert team["icon"] == "shield"
    assert [m["status"] for m in added["created"]] == ["invited", "invited"]
    oleg = next(m for m in added["created"] if m["email"] == "oleg@energo.example")
    assert (anna["audience"], oleg["audience"]) == ("specialist", "management")
    assert len(company["teams"][0]["members"]) == 2

    assert invite.status_code == 200
    assert invite.json()["company"] == "Энергосеть"
    assert invite.json()["team"] == "SOC"
    assert invite.json()["manager"] == "boss"
    assert invite.json()["interests"]
    assert accepted.status_code == 200
    assert me["company"]["role"] == "member"
    assert me["company"]["team"] == "SOC"
    assert me["company"]["job_title"] == "Инженер SOC"
    # A new reader still gets the tour; the profile is already waiting.
    assert me["onboarded_at"] is None
    assert len(profiles) == 1
    assert profiles[0]["team_id"] == team["id"]
    assert profiles[0]["spec"]["role"].startswith("Инженер SOC.")
    assert again.status_code == 404
    assert login.status_code == 200


async def test_a_list_skips_bad_repeated_and_taken_addresses(api: str) -> None:
    async with register(api, "taken") as someone:
        taken = (await someone.get("/auth/me")).json()["email"]
    async with register(api, "boss") as boss:
        await boss.post("/company", json={"name": "Энергосеть"})
        team = await make_team(boss)
        added = await add(
            boss,
            team["id"],
            {"name": "Ира", "email": "ira@energo.example"},
            {"name": "Ира снова", "email": "IRA@energo.example"},
            {"name": "Без почты", "email": "не почта"},
            {"name": "Чужой", "email": taken},
            {"name": "Служебный", "email": "x@radar.local"},
        )

    assert [m["email"] for m in added["created"]] == ["ira@energo.example"]
    assert [item["reason"] for item in added["skipped"]] == [
        "Адрес повторяется в списке.",
        "Проверьте адрес почты.",
        "С этой почтой уже есть аккаунт.",
        "Проверьте адрес почты.",
    ]


async def test_team_changes_reach_profiles_until_their_reader_edits_one(api: str) -> None:
    async with register(api, "boss") as boss:
        await boss.post("/company", json={"name": "Энергосеть"})
        team = await make_team(boss)
        added = await add(
            boss,
            team["id"],
            {"name": "Анна", "email": "anna2@energo.example"},
            {"name": "Борис", "email": "boris@energo.example"},
        )
        anna, boris = added["created"]
        for member in (anna, boris):
            async with client(api) as person:
                await person.post(f"/auth/invite/{token_of(member)}", json={"password": PASSWORD})
                if member is boris:
                    own = (await person.get("/profiles")).json()[0]
                    edited = {**own["spec"], "exclusions": ["реклама"]}
                    await person.put(f"/profiles/{own['id']}", json=edited)

        changed_spec = {**team["spec"], "max_items": 7}
        updated = await boss.put(
            f"/company/teams/{team['id']}",
            json={**SOC, "name": "SOC 24/7", "spec": changed_spec},
        )

    async with client(api) as person:
        await person.post(
            "/auth/login", json={"email": "anna2@energo.example", "password": PASSWORD}
        )
        anna_profile = (await person.get("/profiles")).json()[0]
    async with client(api) as person:
        await person.post(
            "/auth/login", json={"email": "boris@energo.example", "password": PASSWORD}
        )
        boris_profile = (await person.get("/profiles")).json()[0]

    assert updated.status_code == 200
    assert updated.json()["spec"]["name"] == "SOC 24/7"
    assert (anna_profile["spec"]["name"], anna_profile["spec"]["max_items"]) == ("SOC 24/7", 7)
    assert anna_profile["version"] == 2
    # Boris made the profile his own: it keeps his edit and the old team settings.
    assert boris_profile["team_id"] is None
    assert boris_profile["spec"]["exclusions"] == ["реклама"]
    assert boris_profile["spec"]["max_items"] == team["spec"]["max_items"]


async def test_moving_a_member_rewords_the_profile_that_follows_the_team(api: str) -> None:
    async with register(api, "boss") as boss:
        await boss.post("/company", json={"name": "Энергосеть"})
        soc = await make_team(boss)
        network = await make_team(boss, NETWORK)
        member = (await add(boss, soc["id"], {"name": "Вера", "email": "vera@energo.example"}))[
            "created"
        ][0]
        moved = await boss.patch(
            f"/company/members/{member['id']}",
            json={"team_id": network["id"], "job_title": "Руководитель группы сетей"},
        )
        company = (await boss.get("/company")).json()

    async with client(api) as person:
        await person.post(f"/auth/invite/{token_of(member)}", json={"password": PASSWORD})
        profile = (await person.get("/profiles")).json()[0]

    assert moved.status_code == 200
    assert moved.json()["team_id"] == network["id"]
    assert moved.json()["audience"] == "management"
    assert [len(team["members"]) for team in company["teams"]] == [0, 1]
    assert profile["team_id"] == network["id"]
    assert profile["spec"]["name"] == "Сети"
    assert profile["spec"]["audience"] == "management"
    assert profile["spec"]["role"].startswith("Руководитель группы сетей.")


async def test_links_can_be_renewed_and_people_removed(api: str) -> None:
    async with register(api, "boss") as boss:
        await boss.post("/company", json={"name": "Энергосеть"})
        team = await make_team(boss)
        first, second = (
            await add(
                boss,
                team["id"],
                {"name": "Глеб", "email": "gleb@energo.example"},
                {"name": "Дина", "email": "dina@energo.example"},
            )
        )["created"]
        renewed = await boss.post(f"/company/members/{first['id']}/invite")
        refused_delete = await boss.delete(f"/company/teams/{team['id']}")

        async with client(api) as dina:
            await dina.post(f"/auth/invite/{token_of(second)}", json={"password": PASSWORD})
            active_renew = await boss.post(f"/company/members/{second['id']}/invite")
            removed = await boss.delete(f"/company/members/{second['id']}")
            after_removal = (await dina.get("/auth/me")).json()

        async with client(api) as visitor:
            old_link = await visitor.get(f"/auth/invite/{token_of(first)}")
            new_link = await visitor.get(f"/auth/invite/{token_of(renewed.json())}")
        await boss.delete(f"/company/members/{first['id']}")
        emptied = await boss.delete(f"/company/teams/{team['id']}")
        company = (await boss.get("/company")).json()

    assert renewed.status_code == 200
    assert token_of(renewed.json()) != token_of(first)
    assert old_link.status_code == 404
    assert new_link.status_code == 200
    assert refused_delete.status_code == 409
    assert active_renew.status_code == 409
    assert removed.status_code == 204
    assert after_removal is None
    assert emptied.status_code == 204
    assert company["teams"] == []


async def test_a_space_reaches_only_its_own_teams_and_people(api: str) -> None:
    async with register(api, "boss") as boss, register(api, "other") as other:
        await boss.post("/company", json={"name": "Энергосеть"})
        team = await make_team(boss)
        member = (await add(boss, team["id"], {"name": "Лев", "email": "lev@energo.example"}))[
            "created"
        ][0]
        await other.post("/company", json={"name": "Другая"})
        other_team = await other.put(f"/company/teams/{team['id']}", json=SOC)
        other_add = await other.post(
            f"/company/teams/{team['id']}/members",
            json={"people": [{"email": "x@energo.example"}]},
        )
        other_move = await other.patch(f"/company/members/{member['id']}", json={})
        other_remove = await other.delete(f"/company/members/{member['id']}")
        second_space = await boss.post("/company", json={"name": "Ещё одна"})

    async with client(api) as lev:
        await lev.post(f"/auth/invite/{token_of(member)}", json={"password": PASSWORD})
        own_space = await lev.post("/company", json={"name": "Своя"})
    async with client(api) as guest:
        await guest.post("/auth/demo")
        guest_space = await guest.post("/company", json={"name": "Гостевая"})
    async with client(api) as visitor:
        nobody = await visitor.get("/company")
        bad_link = await visitor.get("/auth/invite/" + "x" * 32)

    assert other_team.status_code == 404
    assert other_add.status_code == 404
    assert other_move.status_code == 404
    assert other_remove.status_code == 404
    assert second_space.status_code == 409
    assert own_space.status_code == 409
    assert guest_space.status_code == 403
    assert nobody.status_code == 401
    assert bad_link.status_code == 404


async def test_an_invitation_works_while_registration_is_closed(api: str, monkeypatch: Any) -> None:
    async with register(api, "boss") as boss:
        await boss.post("/company", json={"name": "Энергосеть"})
        team = await make_team(boss)
        member = (await add(boss, team["id"], {"name": "Ия", "email": "iya@energo.example"}))[
            "created"
        ][0]

    from radar.config import get_settings

    monkeypatch.setenv("RADAR_REGISTRATION_OPEN", "false")
    get_settings.cache_clear()
    try:
        async with client(api) as person:
            short = await person.post(
                f"/auth/invite/{token_of(member)}", json={"password": "short"}
            )
            accepted = await person.post(
                f"/auth/invite/{token_of(member)}", json={"password": PASSWORD}
            )
    finally:
        monkeypatch.delenv("RADAR_REGISTRATION_OPEN")
        get_settings.cache_clear()

    assert short.status_code == 422
    assert accepted.status_code == 200
