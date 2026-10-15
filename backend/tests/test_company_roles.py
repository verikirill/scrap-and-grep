"""A team's profile from its description, and each member's copy of it."""

from dataclasses import replace
from typing import Any

import pytest
from pydantic import BaseModel

from radar.ai.resilient import CircuitBreaker
from radar.company.roles import (
    HeuristicTeamDrafter,
    ModelTeamDrafter,
    ResilientTeamDrafter,
    TeamBrief,
    audience_for,
    member_spec,
    team_color,
    team_icon,
)
from radar.domain import ProfileSpec

SOC = TeamBrief(
    company="Энергосеть",
    about="Распределение электроэнергии в трёх регионах.",
    team="SOC",
    services=(
        "Круглосуточный мониторинг событий ИБ в MaxPatrol SIEM, реагирование на инциденты "
        "и расследования. Ведём правила корреляции и EDR на рабочих станциях."
    ),
    systems=("MaxPatrol SIEM",),
)


class _Chat:
    """A model that answers with what the test gave it, or fails."""

    name = "test-model"

    def __init__(self, answer: dict[str, Any] | None = None) -> None:
        self.answer = answer
        self.asked: list[str] = []

    async def ask[T: BaseModel](self, schema: type[T], system: str, user: str) -> T:
        self.asked.append(user)
        if self.answer is None:
            raise TimeoutError("the model did not answer")
        return schema.model_validate(self.answer)


ANSWER = {
    "role": "Команда SOC ведёт круглосуточный мониторинг и отвечает за реагирование.",
    "systems": ["Kaspersky EDR", "MaxPatrol SIEM"],
    "interests": [
        {
            "title": "Атаки на энергетику",
            "description": "Кампании против сетевых компаний.",
            "keywords": ["APT", "энергетика", "ransomware"],
        },
        {
            "title": "Обнаружение и реагирование",
            "description": "Новые техники и правила SIEM.",
            "keywords": ["SIEM", "EDR", "SOC"],
        },
    ],
}


async def test_the_offline_draft_finds_the_teams_area_in_its_description() -> None:
    spec = await HeuristicTeamDrafter().draft(SOC)

    assert spec.name == "SOC"
    assert spec.interests[0].id == "soc-monitoring"
    assert spec.interests[0].weight == 1.2
    assert spec.role.startswith("Команда «SOC» в компании «Энергосеть». Круглосуточный")
    assert spec.systems == ("MaxPatrol SIEM",)
    assert spec.audience == "specialist"


async def test_a_description_with_nothing_known_still_gets_general_topics() -> None:
    brief = TeamBrief(company="", about="", team="Канцелярия", services="Бумаги и печати.")

    spec = await HeuristicTeamDrafter().draft(brief)

    assert [interest.id for interest in spec.interests] == ["risk-and-incidents", "energy-digital"]
    assert spec.role == "Команда «Канцелярия». Бумаги и печати."


async def test_the_model_draft_keeps_the_managers_systems_first() -> None:
    chat = _Chat(ANSWER)
    brief = replace(SOC, services="Мониторинг <b>SIEM</b>")

    spec = await ModelTeamDrafter(chat).draft(brief)  # type: ignore[arg-type]

    # «MaxPatrol SIEM» from the manager and from the model is one system.
    assert spec.systems == ("MaxPatrol SIEM", "Kaspersky EDR")
    assert [interest.id for interest in spec.interests] == ["team-1", "team-2"]
    assert spec.name == "SOC"
    # The description cannot close the tag it is wrapped in.
    assert "<b>" not in chat.asked[0]
    assert chat.asked[0].startswith("<team>\nКоманда: SOC")


async def test_a_failing_model_falls_back_to_the_offline_draft() -> None:
    breaker = CircuitBreaker(failure_threshold=1, reset_seconds=60)
    drafter = ResilientTeamDrafter(
        ModelTeamDrafter(_Chat(None)),  # type: ignore[arg-type]
        HeuristicTeamDrafter(),
        breaker,
    )

    first = await drafter.draft(SOC)
    second = await drafter.draft(SOC)

    assert first.interests[0].id == "soc-monitoring"
    assert second == first
    assert not breaker.allow()


@pytest.mark.parametrize(
    ("title", "audience"),
    [
        ("Начальник отдела эксплуатации", "management"),
        ("Директор по ИТ", "management"),
        ("CISO", "management"),
        ("Тимлид SOC", "specialist"),
        ("Ведущий инженер", "specialist"),
        ("", "specialist"),
        (None, "specialist"),
    ],
)
def test_managers_read_the_brief_and_everyone_else_the_cards(
    title: str | None, audience: str
) -> None:
    assert audience_for(title) == audience


async def test_a_member_gets_the_team_profile_worded_for_their_position() -> None:
    team = await HeuristicTeamDrafter().draft(SOC)

    engineer = member_spec(team, "Инженер SOC")
    head = member_spec(team, "Руководитель SOC")
    nobody = member_spec(team, None)

    assert engineer.role.startswith("Инженер SOC. Команда «SOC»")
    assert engineer.interests == team.interests
    assert engineer.audience == "specialist"
    assert head.audience == "management"
    assert nobody == team
    assert isinstance(engineer, ProfileSpec)


def test_a_team_gets_an_icon_from_its_work_and_colours_go_round() -> None:
    assert team_icon("Эксплуатация АСУ ТП подстанций") == "factory"
    assert team_icon("SOC: мониторинг SIEM") == "shield"
    assert team_icon("Сетевая инфраструктура и VPN") == "network"
    assert team_icon("Бухгалтерия") == "work"
    assert team_color(0) == "blue"
    assert team_color(9) == team_color(0)
