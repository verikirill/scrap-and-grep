"""A change to many profiles at once: topics in or out, exclusions, products,
the format and the size of a digest.

The manager makes one change and picks who gets it: the whole team, everyone
with one role, or chosen people. For a team or a role the change goes into
their profile; for people it is kept with each person and laid over whatever
their team or role says, so a later change of the team does not undo it.
"""

from collections.abc import Iterable, Sequence
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from radar.domain import Audience, Interest, ProfileSpec
from radar.text import stable_hash

# Kept with a person: enough for any real sequence of edits, small for a row.
MAX_PERSONAL_PATCHES = 30
Phrase = Annotated[str, Field(min_length=1, max_length=120)]


class NewInterest(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=600)
    keywords: tuple[Annotated[str, Field(min_length=1, max_length=80)], ...] = Field(
        default=(), max_length=30
    )


class ProfilePatch(BaseModel):
    """Only what is set changes; an empty patch changes nothing."""

    model_config = ConfigDict(frozen=True)

    add_interests: tuple[NewInterest, ...] = Field(default=(), max_length=10)
    # By title, as the manager sees them; case does not matter.
    remove_interests: tuple[Phrase, ...] = Field(default=(), max_length=20)
    add_exclusions: tuple[Phrase, ...] = Field(default=(), max_length=20)
    remove_exclusions: tuple[Phrase, ...] = Field(default=(), max_length=20)
    add_systems: tuple[Annotated[str, Field(min_length=1, max_length=80)], ...] = Field(
        default=(), max_length=20
    )
    audience: Audience | None = None
    max_items: int | None = Field(default=None, ge=3, le=60)
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)

    def is_empty(self) -> bool:
        return self == ProfilePatch()


class PatchError(ValueError):
    """The change would leave a profile the service cannot use. The message is
    written for the manager."""


def _fold(values: Iterable[str]) -> set[str]:
    return {value.strip().casefold() for value in values}


def _interest_id(title: str) -> str:
    # Stable for a title: the same topic added twice is one interest, and the
    # marks a reader made on it keep pointing at it.
    return "added-" + stable_hash(title.casefold())[:10]


def apply_patch(spec: ProfileSpec, patch: ProfilePatch) -> ProfileSpec:
    removed = _fold(patch.remove_interests)
    interests = [item for item in spec.interests if item.title.casefold() not in removed]
    known = _fold(item.title for item in interests)
    for new in patch.add_interests:
        if new.title.strip().casefold() in known:
            continue
        known.add(new.title.strip().casefold())
        interests.append(
            Interest(
                id=_interest_id(new.title.strip()),
                title=new.title.strip(),
                description=new.description.strip(),
                keywords=new.keywords,
            )
        )
    if not interests:
        raise PatchError("В профиле должна остаться хотя бы одна тема.")
    if len(interests) > 20:
        raise PatchError("В профиле может быть не больше 20 тем.")

    dropped = _fold(patch.remove_exclusions)
    exclusions = [item for item in spec.exclusions if item.casefold() not in dropped]
    exclusions += [
        item for item in patch.add_exclusions if item.casefold() not in _fold(exclusions)
    ]

    changes: dict[str, Any] = {
        "interests": [item.model_dump(mode="json") for item in interests],
        "exclusions": exclusions[:20],
        "systems": [*spec.systems, *patch.add_systems][:40],
    }
    if patch.audience is not None:
        changes["audience"] = patch.audience
    if patch.max_items is not None:
        changes["max_items"] = patch.max_items
    if patch.min_score is not None:
        changes["min_score"] = patch.min_score
    return ProfileSpec.model_validate({**spec.model_dump(mode="json"), **changes})


def apply_all(spec: ProfileSpec, patches: Sequence[dict[str, Any]]) -> ProfileSpec:
    """A person's own changes over their team's profile, oldest first. One that
    no longer fits (it would remove the last topic) is passed over."""
    for raw in patches:
        try:
            spec = apply_patch(spec, ProfilePatch.model_validate(raw))
        except ValueError:
            continue
    return spec
