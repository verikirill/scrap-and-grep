"""Side experiments for the recommender: clustering of likes and the variety knob.

    uv run python scripts/experiment_recsys.py --end 2026-09-30T16:00:00+00:00

Uses the same readers, reference grades and simulation as eval_recsys.py
(run that first: it produces the grades). Prints tables for docs/DECISIONS.md.
"""

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from eval_recsys import (
    PERSONAS,
    RELEVANT_FROM,
    SCREENS,
    World,
    _variety,
    build_embedder,
    build_reader,
    ids,
    quality,
    rank,
    signals_for,
)
from eval_retrieval import grade_all, load_articles

from radar import aio
from radar.db import session_scope
from radar.recsys import taste as taste_module
from radar.recsys.ranking import Weights, rerank_for_variety
from radar.store.articles import load_vectors

from radar.recsys import store  # isort: skip


async def learning_gain(world: World, readers: list, weights: Weights) -> tuple[float, float]:
    """Mean nDCG@TOP after one screen of reactions, and its mean change."""
    after_values, deltas = [], []
    for reader in readers:
        for declared in ((reader.resume,), (*reader.interests, reader.resume)):
            before = ids(await rank(world, declared, [], weights))
            for shown in SCREENS:
                screen = before[:shown]
                liked = {i for i in screen if reader.grades.get(i, 0) >= RELEVANT_FROM}
                disliked = {i for i in screen if reader.grades.get(i, 0) == 0}
                rest = set(world.articles) - set(screen)
                after = ids(
                    await rank(world, declared, signals_for(world, liked, disliked), weights)
                )
                base = quality(before, reader, rest)[0]
                tuned = quality(after, reader, rest)[0]
                after_values.append(tuned)
                deltas.append(tuned - base)
    return float(np.mean(after_values)), float(np.mean(deltas))


async def main(args: argparse.Namespace) -> None:
    end = datetime.fromisoformat(args.end) if args.end else datetime.now(UTC)
    start = end - timedelta(days=args.days)
    out = Path(args.out)
    embedder = build_embedder(args.embedding)
    articles = await load_articles(start, end)
    async with session_scope() as session:
        vectors = await load_vectors(session, embedder.model_id, [a.id for a in articles])
    world = World(
        embedder=embedder,
        scope=store.Scope(start=start, end=end),
        articles={article.id: article for article in articles},
        vectors=vectors,
    )
    readers = []
    for persona in PERSONAS:
        grades = await grade_all(articles, persona.profile, out / persona.grades_file, args.judge)
        readers.append(await build_reader(persona, world, grades))
    weights = Weights()

    print("| Лайков на один центр | Центров не больше | nDCG@20 после оценок | Прирост |")
    print("|---|---|---|---|")
    for per_facet, max_facets in ((4, 4), (3, 4), (3, 6), (2, 6), (1, 12)):
        taste_module._SIGNALS_PER_FACET = per_facet
        taste_module.MAX_LEARNED_FACETS = max_facets
        after, delta = await learning_gain(world, readers, weights)
        print(f"| {per_facet} | {max_facets} | {after:.3f} | {delta:+.3f} |", flush=True)
    taste_module._SIGNALS_PER_FACET, taste_module.MAX_LEARNED_FACETS = 4, 4

    print()
    print("| Вес релевантности | nDCG@20 | Близость пар в топ-20 | Источников в топ-20 |")
    print("|---|---|---|---|")
    sources = {article_id: article.source_id for article_id, article in world.articles.items()}
    for variety in (1.0, 0.95, 0.9, 0.85, 0.75):
        scores, similarity, distinct = [], [], []
        for reader in readers:
            ranked = await rank(world, (*reader.interests, reader.resume), [], weights)
            order = ids(
                rerank_for_variety(
                    [item for item in ranked if item.score >= weights.min_score][:240],
                    world.vectors,
                    sources,
                    duplicate_threshold=embedder.duplicate_threshold,
                    variety=variety,
                    limit=120,
                )
            )
            scores.append(quality(order, reader, set(world.articles))[0])
            pair, count = _variety(world, order)
            similarity.append(pair)
            distinct.append(count)
        print(
            f"| {variety} | {np.mean(scores):.3f} | {np.mean(similarity):.3f} "
            f"| {np.mean(distinct):.1f} |",
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--end", default=None)
    parser.add_argument("--judge", default="qwen3.5:9b")
    parser.add_argument("--embedding", default="embeddinggemma:300m")
    parser.add_argument("--out", default="../docs/eval")
    aio.run(main(parser.parse_args()))
