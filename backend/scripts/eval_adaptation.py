"""Does a profile that follows its reader find more of what the reader wants?

    uv run python scripts/eval_adaptation.py --end 2026-09-30T18:00:00+00:00 --out ../docs/eval

Scenario. A reader imports someone else's profile, or keeps their own. For the
first days of the week the digest shows them the profile's top articles; they
like what is relevant to them, dislike what is not at all, and scroll past the
rest. The profile then adapts (recsys.adapt: weights by the like rate, the
meaning of each interest by Rocchio's relevance feedback), and articles the
profile did not cover but the reader liked become a suggested interest.
Quality is measured on the following days, which the reader has not seen: the
articles are ranked the way digest retrieval ranks them (the hybrid score of
the best interest times its weight), with and without what was learned.

The reference is the same as in eval_recsys.py: the grades the language model
gave every article of the week for each persona's own profile (0-3), cached in
docs/eval. "The reader" is that persona; relevant means grade >= 2. It says
how well the ranking agrees with the grader the pipeline trusts, not what a
person would say.
"""

import argparse
import json
import math
import random
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from eval_recsys import PERSONAS, Persona, build_embedder
from eval_retrieval import load_articles

from radar import aio
from radar.ai.embedder import Embedder
from radar.db import session_scope
from radar.db.models import Article
from radar.domain import Interest, ProfileSpec
from radar.ingest.service import embed_pending
from radar.recsys import store
from radar.recsys.adapt import adapt_interest, groups_of, title_key
from radar.recsys.adaptation import ATTRIBUTE_FROM, COVERED_FROM
from radar.recsys.model import Learned, adapted_weight
from radar.recsys.naming import name_interest
from radar.recsys.ranking import Evidence
from radar.recsys.taste import Facet, Signal
from radar.selection.retrieval import keyword_query
from radar.selection.scoring import LEXICAL_BONUS, lexical_score, retrieval_score
from radar.store.articles import load_vectors

RELEVANT_FROM = 2
SHOWN = 30
TOP = 20
HEAD = 10
TRAIN_SHARE = 4 / 7
# Candidates per interest, as in digest retrieval (per_interest_limit).
PER_INTEREST = 40
FEED_SEEN = 120


@dataclass(frozen=True, slots=True)
class Week:
    embedder_id: str
    semantic: bool
    articles: dict[int, Article]
    vectors: dict[int, np.ndarray]
    train: tuple[datetime, datetime]
    test: tuple[datetime, datetime]


def grades_of(persona: Persona, out: Path, articles: dict[int, Article]) -> dict[int, int]:
    stored = json.loads((out / persona.grades_file).read_text("utf-8"))["grades"]
    by_url = {article.url: article_id for article_id, article in articles.items()}
    return {by_url[url]: grade for url, grade in stored.items() if url in by_url}


async def facets_of(profile: ProfileSpec, embedder: Embedder) -> list[Facet]:
    vectors = await embedder.embed([i.as_query() for i in profile.interests], "query")
    return [
        Facet(
            key=interest.id,
            kind="interest",
            label=interest.title,
            vector=np.asarray(vector, dtype=np.float32),
            weight=interest.weight,
            query=keyword_query(interest.keywords or (interest.title,)),
        )
        for interest, vector in zip(profile.interests, vectors, strict=True)
    ]


async def evidence(
    week: Week, span: tuple[datetime, datetime], facets: list[Facet]
) -> list[Evidence]:
    ids = [i for i, a in week.articles.items() if span[0] <= a.published_at < span[1]]
    async with session_scope() as session:
        return await store.evidence(
            session,
            model=week.embedder_id,
            scope=store.Scope(start=span[0], end=span[1]),
            facets=facets,
            include=ids,
        )


def uncapped(item: Evidence, facet: Facet, semantic: bool) -> float:
    """The retrieval score before it is capped at 1.

    Capped, a large share of the top articles scores exactly 1 and their order
    is decided by the tie-break, not by the evidence; an evaluation of the
    order must see past the cap. (In a digest the language model's grade is
    mixed in and ties are rare.)
    """
    z = item.z.get(facet.key, 0.0)
    lexical = facet.key in item.rank_share
    if semantic:
        return 0.2 + 0.18 * z + (LEXICAL_BONUS if lexical else 0.0)
    return lexical_score(item.rank_share.get(facet.key, 0.0), z, lexical)


def best_match(item: Evidence, facets: list[Facet], semantic: bool) -> tuple[str | None, float]:
    best, top = None, 0.0
    for facet in facets:
        z = item.z.get(facet.key, 0.0)
        lexical = facet.key in item.rank_share
        score = (
            retrieval_score(z, lexical)
            if semantic
            else lexical_score(item.rank_share.get(facet.key, 0.0), z, lexical)
        )
        if score > top:
            best, top = facet.key, score
    return best, top


@dataclass(frozen=True, slots=True)
class Ranking:
    order: list[int]
    # Article -> the interest that would bring it in, and how strongly.
    matches: dict[int, tuple[str | None, float]]
    # What digest retrieval would hand to the grader: each interest's best PER_INTEREST.
    pool: set[int]


async def ranking(
    week: Week, span: tuple[datetime, datetime], facets: list[Facet], weights: dict[str, float]
) -> Ranking:
    """Articles of the span best first, scored like digest retrieval."""
    found = await evidence(week, span, facets)
    scored: dict[int, float] = {}
    matches: dict[int, tuple[str | None, float]] = {}
    per_facet: dict[str, list[tuple[float, int]]] = {facet.key: [] for facet in facets}
    for item in found:
        matches[item.article_id] = best_match(item, facets, week.semantic)
        best = 0.0
        for facet in facets:
            raw = uncapped(item, facet, week.semantic)
            per_facet[facet.key].append((raw, item.article_id))
            best = max(best, raw * weights.get(facet.key, 1.0))
        scored[item.article_id] = best
    pool = {
        article_id
        for hits in per_facet.values()
        for _, article_id in sorted(hits, reverse=True)[:PER_INTEREST]
    }
    return Ranking(sorted(scored, key=lambda i: (-scored[i], i)), matches, pool)


def ndcg(order: list[int], grades: dict[int, int], depth: int) -> float:
    gain = sum(
        (2 ** grades.get(i, 0) - 1) / math.log2(rank + 2) for rank, i in enumerate(order[:depth])
    )
    best = sorted(grades.values(), reverse=True)[:depth]
    ideal = sum((2**g - 1) / math.log2(rank + 2) for rank, g in enumerate(best))
    return gain / ideal if ideal else 0.0


def precision(order: list[int], grades: dict[int, int], depth: int) -> float:
    return sum(1 for i in order[:depth] if grades.get(i, 0) >= RELEVANT_FROM) / depth


def signal(week: Week, article_id: int, kind: str) -> Signal:
    article = week.articles[article_id]
    return Signal(
        article_id, kind, 0.0, article.source_id, article.title, week.vectors.get(article_id)
    )


@dataclass(frozen=True, slots=True)
class Result:
    name: str
    ndcg: float
    precision: float
    recall: float


@dataclass(frozen=True, slots=True)
class Run:
    reader: str
    profile: str
    results: list[Result]
    note: str


async def run(
    week: Week, embedder: Embedder, reader: Persona, profile: ProfileSpec, grades: dict[int, int]
) -> Run:
    facets = await facets_of(profile, embedder)
    stated = {facet.key: facet.weight for facet in facets}
    first = await ranking(week, week.train, facets, stated)
    train_matches = first.matches
    shown = [i for i in first.order if i in grades][:SHOWN]
    liked = [i for i in shown if grades[i] >= RELEVANT_FROM]
    disliked = [i for i in shown if grades[i] == 0]
    skipped = [i for i in shown if i not in liked and i not in disliked]

    def owner(article_id: int) -> str | None:
        key, score = train_matches.get(article_id, (None, 0.0))
        return key if score >= ATTRIBUTE_FROM else None

    marks = [signal(week, i, "like") for i in liked] + [
        signal(week, i, "dislike") for i in disliked
    ]
    learned: dict[str, Learned] = {}
    for facet in facets:
        state = adapt_interest(
            facet.key,
            facet.vector,
            [mark for mark in marks if owner(mark.article_id) == facet.key],
            [0.0 for i in skipped if owner(i) == facet.key],
        )
        learned[facet.key] = Learned(
            factor=state.factor,
            vector=None if state.vector is None else state.vector.tolist(),
            drift=state.drift,
        )

    # Liked articles no interest covers come from the feed, which shows more than
    # the profile finds. The reader is taken to have scrolled through FEED_SEEN
    # articles of the first days besides the digest, the same for every run.
    train_ids = sorted(
        i for i, a in week.articles.items() if week.train[0] <= a.published_at < week.train[1]
    )
    feed = random.Random(reader.key).sample(train_ids, min(FEED_SEEN, len(train_ids)))  # noqa: S311
    uncovered = [
        (1.0, signal(week, i, "like"))
        for i in sorted(set(feed) | set(liked))
        if grades.get(i, 0) >= RELEVANT_FROM and train_matches.get(i, (None, 0.0))[1] < COVERED_FROM
    ]
    suggested: list[Interest] = []
    names = {title_key(interest.title) for interest in profile.interests}
    for index, group in enumerate(groups_of(uncovered, min_size=3, max_groups=2)):
        draft = await name_interest([s.title for s in group])
        # As in the product: one suggestion per name.
        if title_key(draft.title) in names:
            continue
        names.add(title_key(draft.title))
        suggested.append(
            Interest(
                id=f"suggested-{index}",
                title=draft.title[:120] if len(draft.title) >= 2 else "Тема",
                description=draft.description[:600],
                keywords=draft.keywords,
            )
        )

    test_grades = {
        i: g
        for i, g in grades.items()
        if week.test[0] <= week.articles[i].published_at < week.test[1]
    }

    def moved(facet: Facet, use_vector: bool) -> Facet:
        own = learned.get(facet.key)
        if not use_vector or own is None or own.vector is None:
            return facet
        return replace(facet, vector=np.asarray(own.vector, dtype=np.float32))

    weighted = {facet.key: adapted_weight(facet.weight, learned.get(facet.key)) for facet in facets}
    variants = {
        "как записан": (facets, stated),
        "только веса": (facets, weighted),
        "только смысл": ([moved(facet, True) for facet in facets], stated),
        "веса и смысл": ([moved(facet, True) for facet in facets], weighted),
    }
    if suggested:
        extra = await facets_of(
            profile.model_copy(update={"interests": tuple(suggested)}), embedder
        )
        both = [moved(facet, True) for facet in facets]
        variants["веса, смысл и принятые предложения"] = (
            [*both, *extra],
            {**weighted, **{facet.key: facet.weight for facet in extra}},
        )

    relevant = {i for i, g in test_grades.items() if g >= RELEVANT_FROM}
    results = []
    for name, (variant_facets, variant_weights) in variants.items():
        found = await ranking(week, week.test, variant_facets, variant_weights)
        order = [i for i in found.order if i in test_grades]
        results.append(
            Result(
                name,
                ndcg(order, test_grades, TOP),
                precision(order, test_grades, HEAD),
                len(found.pool & relevant) / len(relevant) if relevant else 0.0,
            )
        )
    drift = max((item.drift for item in learned.values()), default=0.0)
    factors = ", ".join(f"{item.factor:.2f}" for item in learned.values())
    titles = "; ".join(f"«{item.title}»" for item in suggested)
    note = (
        f"отметки: {len(liked)} нравится, {len(disliked)} не то, {len(skipped)} пролистано; "
        f"веса ×[{factors}]; сдвиг смысла до {drift:.3f}; предложено: {titles or 'ничего'}"
    )
    return Run(reader.key, profile.name, results, note)


def rows_of(item: Run) -> list[str]:
    return [
        *(
            f"| {item.reader} | {item.profile} | {result.name} | {result.ndcg:.3f} "
            f"| {result.precision:.2f} | {result.recall:.2f} |"
            for result in item.results
        ),
        f"| | | {item.note} | | | |",
    ]


async def main(args: argparse.Namespace) -> None:
    end = datetime.fromisoformat(args.end) if args.end else datetime.now(UTC)
    start = end - timedelta(days=args.days)
    split = start + (end - start) * TRAIN_SHARE
    out = Path(args.out)
    embedder = build_embedder(args.embedding)
    await embed_pending(embedder, since=start, until=end, max_articles=100_000)
    articles = await load_articles(start, end)
    async with session_scope() as session:
        vectors = await load_vectors(session, embedder.model_id, [a.id for a in articles])
    week = Week(
        embedder_id=embedder.model_id,
        semantic=embedder.semantic,
        articles={article.id: article for article in articles},
        vectors=vectors,
        train=(start, split),
        test=(split, end),
    )
    report = [
        f"Период: {start:%d.%m.%Y} - {end:%d.%m.%Y}, статей: {len(articles)}. Отметки ставятся "
        f"по {split:%d.%m %H:%M}, качество считается после. Эмбеддер: {embedder.model_id}. "
        f"Читатель отмечает первые {SHOWN} статей своей подборки: нравится при оценке "
        f"эталона от {RELEVANT_FROM}, не то при оценке 0, остальное пролистано.",
        "",
        f"| Читатель | Профиль | Подстройка | nDCG@{TOP} | P@{HEAD} | Полнота кандидатов |",
        "|---|---|---|---|---|---|",
    ]
    for reader in PERSONAS:
        grades = grades_of(reader, out, week.articles)
        for profile_owner in PERSONAS:
            report += rows_of(await run(week, embedder, reader, profile_owner.profile, grades))
    text = "\n".join(report) + "\n"
    # LF on every system: Windows would write CRLF into a file kept in git.
    (out / "adaptation.md").write_text(text, "utf-8", newline="\n")
    print(text.encode("utf-8", "replace").decode("ascii", "replace") if args.quiet else text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--end", default=None, help="End of the period, ISO 8601; now if omitted.")
    parser.add_argument("--embedding", default="embeddinggemma:300m")
    parser.add_argument("--out", default="../docs/eval")
    parser.add_argument("--quiet", action="store_true", help="Do not print the report.")
    aio.run(main(parser.parse_args()))
