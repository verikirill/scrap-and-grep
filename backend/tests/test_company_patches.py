"""One change for many profiles, and the role a position names."""

from types import SimpleNamespace
from typing import Any, cast

import pytest

from radar.company.patches import NewInterest, PatchError, ProfilePatch, apply_all, apply_patch
from radar.company.service import match_role
from radar.db.models import TeamRole
from radar.domain import Interest, ProfileSpec

BASE = ProfileSpec(
    name="SOC",
    interests=(
        Interest(id="soc", title="Мониторинг и реагирование", keywords=("SIEM",)),
        Interest(id="ics", title="Безопасность АСУ ТП", keywords=("SCADA",)),
    ),
    exclusions=("вакансии",),
    systems=("MaxPatrol SIEM",),
)
CLOUD = NewInterest(title="Облачные сервисы", keywords=("SaaS", "облако"))


def test_a_change_adds_and_removes_topics_and_sets_the_format() -> None:
    patch = ProfilePatch(
        add_interests=(CLOUD,),
        remove_interests=("безопасность асу тп",),
        add_exclusions=("реклама",),
        remove_exclusions=("Вакансии",),
        add_systems=("Kaspersky EDR",),
        audience="management",
        max_items=12,
    )

    spec = apply_patch(BASE, patch)

    assert [item.title for item in spec.interests] == [
        "Мониторинг и реагирование",
        "Облачные сервисы",
    ]
    assert spec.exclusions == ("реклама",)
    assert spec.systems == ("MaxPatrol SIEM", "Kaspersky EDR")
    assert (spec.audience, spec.max_items) == ("management", 12)
    # The same topic added again elsewhere keeps one id: marks on it stay put.
    again = apply_patch(BASE, ProfilePatch(add_interests=(CLOUD,)))
    assert again.interests[-1].id == spec.interests[-1].id


def test_a_change_that_leaves_no_topic_is_refused_and_skipped_in_a_sequence() -> None:
    everything = ProfilePatch(remove_interests=("Мониторинг и реагирование", "Безопасность АСУ ТП"))

    with pytest.raises(PatchError):
        apply_patch(BASE, everything)
    kept = apply_all(BASE, [everything.model_dump(mode="json"), {"max_items": 9}])
    assert len(kept.interests) == 2
    assert kept.max_items == 9


def _role(name: str) -> TeamRole:
    return cast(TeamRole, SimpleNamespace(name=name))


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Ведущий аналитик SOC", "Аналитик ИБ"),
        ("аналитика угроз", "Аналитик ИБ"),
        ("Инженер по защите АСУ ТП", "Инженер АСУ ТП"),
        ("Руководитель SOC", None),
        (None, None),
    ],
)
def test_a_position_finds_the_role_it_names(title: str | None, expected: Any) -> None:
    roles = [_role("Аналитик ИБ"), _role("Инженер АСУ ТП")]

    found = match_role(title, roles)

    assert (found.name if found else None) == expected
