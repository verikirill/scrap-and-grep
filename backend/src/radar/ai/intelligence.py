"""The judgement and writing steps of the digest, behind one interface."""

from collections.abc import Sequence
from typing import Protocol

from radar.domain import (
    Candidate,
    DigestOverview,
    Grade,
    Interest,
    ItemSummary,
    ProfileSpec,
    SelectedItem,
    Topic,
    TopicName,
)


class Intelligence(Protocol):
    name: str

    async def grade(self, candidate: Candidate, profile: ProfileSpec) -> Grade:
        """Decide how relevant one article is for the profile."""
        ...

    async def summarize(
        self, item: SelectedItem, profile: ProfileSpec, interest: Interest | None
    ) -> ItemSummary:
        """Write the digest entry for a selected article."""
        ...

    async def name_topic(self, items: Sequence[SelectedItem], profile: ProfileSpec) -> TopicName:
        """Name a cluster of related items."""
        ...

    async def overview(self, topics: Sequence[Topic], profile: ProfileSpec) -> DigestOverview:
        """Write the digest title and the key takeaways."""
        ...
