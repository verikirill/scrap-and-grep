"""Offline stand-in for the language model.

It grades by retrieval evidence and writes extractive text. The result is
plainer than what a model produces, but it is deterministic, instant and
always available, which makes it both the default for a machine without a GPU
and the fallback when the model server goes down mid-run.
"""

from collections import Counter
from collections.abc import Sequence

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
from radar.selection.scoring import relevance_from_score
from radar.text import STOPWORDS, split_sentences, tokenize, truncate

SUMMARY_LIMIT = 380
_MIN_SENTENCE_LENGTH = 40
_MIN_TEASER_LENGTH = 120
_EXACT_MATCH_LENGTH = 4


class HeuristicIntelligence:
    name = "heuristic"

    async def grade(self, candidate: Candidate, profile: ProfileSpec) -> Grade:
        interest = profile.interest(candidate.interest_id)
        title = interest.title if interest else candidate.interest_id
        hits = _matched_keywords(candidate, interest)
        evidence = f"ключевые слова: {', '.join(hits)}" if hits else "близость по содержанию"
        return Grade(
            relevance=relevance_from_score(candidate.retrieval_score),
            interest_id=candidate.interest_id,
            reason=f"Интерес «{title}»: {evidence}.",
            by_model=False,
        )

    async def summarize(
        self, item: SelectedItem, profile: ProfileSpec, interest: Interest | None
    ) -> ItemSummary:
        article = item.article
        summary = truncate(_lead(article.title, article.summary, article.content), SUMMARY_LIMIT)
        return ItemSummary(
            headline=article.title, summary=summary, why=item.graded.grade.reason, by_model=False
        )

    async def name_topic(self, items: Sequence[SelectedItem], profile: ProfileSpec) -> TopicName:
        interest_ids = Counter(item.graded.interest_id for item in items)
        interest = profile.interest(interest_ids.most_common(1)[0][0])
        base = interest.title if interest else "Разное"
        names = _shared_names([item.article.title for item in items])
        title = f"{base}: {', '.join(names)}" if names else base
        return TopicName(title=title, overview="", by_model=False)

    async def overview(self, topics: Sequence[Topic], profile: ProfileSpec) -> DigestOverview:
        leaders = [topic.items[0] for topic in topics if topic.items][:5]
        highlights = tuple(
            (item.text.headline if item.text and item.text.headline else item.article.title)
            for item in leaders
        )
        return DigestOverview(
            title=f"Дайджест для профиля «{profile.name}»", highlights=highlights, by_model=False
        )


def _matched_keywords(candidate: Candidate, interest: Interest | None) -> list[str]:
    """Interest keywords present in the article, compared token by token.

    Long words are matched by prefix so that inflected forms count. Short ones
    must match exactly, otherwise "OT" would be found inside "MikroTik".
    """
    if interest is None:
        return []
    article = candidate.article
    words = set(tokenize(f"{article.title} {article.summary} {article.body(2000)}"))

    def present(token: str) -> bool:
        if len(token) <= _EXACT_MATCH_LENGTH:
            return token in words
        stem = token[: max(_EXACT_MATCH_LENGTH, len(token) - 2)]
        return any(word.startswith(stem) for word in words)

    hits = [
        keyword
        for keyword in interest.keywords
        if (tokens := tokenize(keyword)) and all(present(token) for token in tokens)
    ]
    return hits[:4]


def _lead(title: str, summary: str, content: str | None) -> str:
    """The feed teaser if it says enough, otherwise the first sentences of the text."""
    if len(summary) >= _MIN_TEASER_LENGTH or not content:
        return summary or title
    lines = [
        line.strip() for line in content.splitlines() if line.strip() and line.strip() != title
    ]
    sentences = [
        sentence
        for sentence in split_sentences(" ".join(lines))
        if len(sentence) >= _MIN_SENTENCE_LENGTH
    ]
    return " ".join(sentences[:2]) or summary or title


def _shared_names(titles: Sequence[str], limit: int = 2) -> list[str]:
    """Product and vendor names that recur across titles, e.g. "Cisco, Chrome".

    Only capitalised Latin words and acronyms qualify. Ordinary words shared
    by headlines ("new", "чаще") would make a topic name read like noise.
    """
    spelling: dict[str, str] = {}
    frequency: Counter[str] = Counter()
    for title in titles:
        seen = set()
        # The first word of a headline is capitalised whatever it is.
        for raw in title.replace("«", " ").replace("»", " ").split()[1:]:
            word = raw.strip(".,:;!?()[]\"'")
            if len(word) < 3 or not _looks_like_name(word) or word.lower() in STOPWORDS:
                continue
            spelling.setdefault(word.lower(), word)
            seen.add(word.lower())
        frequency.update(seen)
    shared = [name for name, count in frequency.most_common() if count >= 2]
    return [spelling[name] for name in shared[:limit]]


def _looks_like_name(word: str) -> bool:
    is_acronym = word.isupper() and word.isalpha()
    is_latin_proper = word.isascii() and word[0].isupper()
    return is_acronym or is_latin_proper
