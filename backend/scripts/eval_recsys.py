"""Measure the personal feed on the project's own articles.

    uv run python scripts/eval_recsys.py --end 2026-09-30T18:00:00+00:00 --out ../docs/eval

Questions:

1. How good is the feed before the reader has done anything: from the resume
   alone, from stated interests alone, from both?
2. Does the feed learn? After the reader has reacted to the first screen, is
   the rest ranked better than without those reactions?
3. Does it find an interest the reader never stated, once they start liking
   articles on it?
4. What does the variety re-rank cost in relevance, and what does it buy?

Method. Two simulated readers, each with a profile (the stated interests) and a
sample resume from examples/resumes. The reference for a reader is the grade
the language model gives every article of the period for that reader's profile
(0-3, the prompt of the digest pipeline); "relevant" is grade >= 2. Reactions
are simulated from the same grades: the reader likes what is relevant to them
and dislikes what scored 0. Rankings with and without reactions are always
compared on the same articles, the ones the reader has not reacted to.

The reference is a model's judgement, not a human's. The numbers say how well
the feed agrees with the grader that the digest pipeline trusts, and how the
feed changes with input; they are not a user study.
"""

import argparse
import itertools
import json
import math
import random
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from eval_retrieval import grade_all, load_articles

from radar import aio
from radar.ai.embedder import Embedder, HashingEmbedder, OllamaEmbedder
from radar.ai.factory import embedding_preset
from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import Article
from radar.domain import ProfileSpec
from radar.ingest.service import embed_pending
from radar.recsys import store
from radar.recsys.ranking import Ranked, Weights, rerank_for_variety, score_article
from radar.recsys.taste import Facet, Signal, Taste, build_taste
from radar.resume.extract import HeuristicResumeExtractor
from radar.resume.files import detect_format
from radar.resume.model import ResumeFacts
from radar.resume.parse import parse_builtin
from radar.resume.scrub import scrub
from radar.seed import DEFAULT_PROFILES
from radar.selection.retrieval import keyword_query
from radar.store.articles import load_vectors

RELEVANT_FROM = 2
HEAD = 10
TOP = 20
WIDE = 30
# How many articles of the first screen the simulated reader reacts to.
SCREENS = (10, 20, 30)
# A field with fewer articles of its own than this cannot show a trend.
MIN_FOREIGN = 20
RESUMES = Path(__file__).resolve().parents[2] / "examples" / "resumes"


@dataclass(frozen=True, slots=True)
class Persona:
    key: str
    profile: ProfileSpec
    resume: str
    grades_file: str


PERSONAS = (
    Persona("ИБ АСУ ТП", DEFAULT_PROFILES[0], "ics-security-engineer.pdf", "grades.json"),
    Persona(
        "ИТ-инфраструктура", DEFAULT_PROFILES[1], "it-infrastructure-lead.docx", "grades-infra.json"
    ),
)


@dataclass(frozen=True, slots=True)
class World:
    """Everything that stays fixed while readers are simulated."""

    embedder: Embedder
    scope: store.Scope
    articles: dict[int, Article]
    vectors: dict[int, np.ndarray]


@dataclass(frozen=True, slots=True)
class Reader:
    persona: Persona
    grades: dict[int, int]
    interests: tuple[Facet, ...]
    resume: Facet

    @property
    def relevant(self) -> set[int]:
        return {article_id for article_id, grade in self.grades.items() if grade >= RELEVANT_FROM}


def build_embedder(name: str) -> Embedder:
    if name == "hashing":
        return HashingEmbedder()
    preset = embedding_preset(name)
    return OllamaEmbedder(
        name,
        get_settings().ollama_base_url,
        query_prefix=preset.query_prefix,
        document_prefix=preset.document_prefix,
        dimensions=preset.dimensions,
        duplicate_threshold=preset.duplicate_threshold,
    )


async def resume_facts(file_name: str) -> ResumeFacts:
    """Facts the offline extractor reads from a sample resume (deterministic)."""
    data = (RESUMES / file_name).read_bytes()
    parsed = await parse_builtin(data, detect_format(data, file_name), max_pages=12)
    return (await HeuristicResumeExtractor().extract(scrub(parsed.text))).facts


async def build_reader(persona: Persona, world: World, grades: dict[int, int]) -> Reader:
    facts = await resume_facts(persona.resume)
    interests = persona.profile.interests
    texts = [*(interest.as_query() for interest in interests), facts.as_query()]
    vectors = [np.asarray(v, dtype=np.float32) for v in await world.embedder.embed(texts, "query")]
    return Reader(
        persona=persona,
        grades=grades,
        interests=tuple(
            Facet(
                key=f"interest:{interest.id}",
                kind="interest",
                label=interest.title,
                vector=vector,
                weight=interest.weight,
                query=keyword_query(interest.keywords or (interest.title,)),
            )
            for interest, vector in zip(interests, vectors, strict=False)
        ),
        resume=Facet(
            key="resume",
            kind="resume",
            label=facts.headline,
            vector=vectors[-1],
            query=keyword_query(facts.skills[:15]),
        ),
    )


def signals_for(world: World, liked: set[int], disliked: set[int]) -> list[Signal]:
    def signal(article_id: int, kind: str) -> Signal:
        article = world.articles[article_id]
        return Signal(
            article_id=article_id,
            kind=kind,
            age_days=0.0,
            source_id=article.source_id,
            title=article.title,
            vector=world.vectors.get(article_id),
        )

    return [
        *(signal(article_id, "like") for article_id in sorted(liked)),
        *(signal(article_id, "dislike") for article_id in sorted(disliked)),
    ]


async def rank(
    world: World, declared: tuple[Facet, ...], signals: list[Signal], weights: Weights
) -> list[Ranked]:
    """Score every article of the period for a reader, best first."""
    taste: Taste = build_taste(declared, signals)
    async with session_scope() as session:
        evidence = await store.evidence(
            session,
            model=world.embedder.model_id,
            scope=world.scope,
            facets=taste.facets,
            include=list(world.articles),
        )
    ranked = [
        score_article(item, taste, weights, semantic=world.embedder.semantic) for item in evidence
    ]
    return sorted(ranked, key=lambda item: (-item.score, item.article_id))


def ndcg(order: list[int], grades: dict[int, int], pool: set[int], depth: int) -> float:
    gain = sum(
        (2 ** grades.get(article_id, 0) - 1) / math.log2(position + 2)
        for position, article_id in enumerate(order[:depth])
    )
    best = sorted((grades.get(article_id, 0) for article_id in pool), reverse=True)[:depth]
    ideal = sum((2**grade - 1) / math.log2(position + 2) for position, grade in enumerate(best))
    return gain / ideal if ideal else 0.0


def quality(order: list[int], reader: Reader, pool: set[int]) -> tuple[float, float, float]:
    """nDCG@TOP, precision@HEAD and recall@WIDE within `pool`."""
    order = [article_id for article_id in order if article_id in pool]
    relevant = reader.relevant & pool
    precision = sum(1 for article_id in order[:HEAD] if article_id in relevant) / HEAD
    recall = len(relevant & set(order[:WIDE])) / len(relevant) if relevant else 0.0
    return ndcg(order, reader.grades, pool, TOP), precision, recall


def ids(ranked: list[Ranked]) -> list[int]:
    return [item.article_id for item in ranked]


async def cold_start(world: World, reader: Reader, weights: Weights) -> list[str]:
    everything = set(world.articles)
    newest = sorted(everything, key=lambda i: world.articles[i].published_at, reverse=True)
    variants: list[tuple[str, list[int]]] = [("только свежесть, без персонализации", newest)]
    for name, declared in (
        ("только резюме", (reader.resume,)),
        ("только заявленные интересы", reader.interests),
        ("интересы и резюме", (*reader.interests, reader.resume)),
    ):
        variants.append((name, ids(await rank(world, declared, [], weights))))
    lines = []
    for name, order in variants:
        score, precision, recall = quality(order, reader, everything)
        lines.append(
            f"| {reader.persona.key} | {name} | {score:.3f} | {precision:.2f} | {recall:.3f} |"
        )
    return lines


async def learning(world: World, reader: Reader, weights: Weights) -> list[str]:
    """React to the first screen, then compare rankings of everything else."""
    lines = []
    for name, declared in (
        ("только резюме", (reader.resume,)),
        ("интересы и резюме", (*reader.interests, reader.resume)),
    ):
        before = ids(await rank(world, declared, [], weights))
        for shown in SCREENS:
            screen = before[:shown]
            liked = {i for i in screen if reader.grades.get(i, 0) >= RELEVANT_FROM}
            disliked = {i for i in screen if reader.grades.get(i, 0) == 0}
            rest = set(world.articles) - set(screen)
            after = ids(await rank(world, declared, signals_for(world, liked, disliked), weights))
            base, base_p, _ = quality(before, reader, rest)
            tuned, tuned_p, _ = quality(after, reader, rest)
            lines.append(
                f"| {reader.persona.key} | {name} | {shown} | {len(liked)} / {len(disliked)} "
                f"| {base:.3f} | {tuned:.3f} | {base_p:.2f} | {tuned_p:.2f} |"
            )
    return lines


async def hidden_interest(
    world: World, reader: Reader, other: Reader, weights: Weights, seeds: int = 5
) -> list[str]:
    """The reader's profile says one thing, their likes say another as well."""
    declared = (*reader.interests, reader.resume)
    before = ids(await rank(world, declared, [], weights))
    # What belongs to the other reader's field and not to this one's.
    foreign = sorted(other.relevant - reader.relevant)
    if len(foreign) < MIN_FOREIGN:
        return [
            f"| {reader.persona.key} | {other.persona.key} | - | {len(foreign)} | - | - | - | - |"
        ]
    lines = []
    for likes in (3, 6, 10):
        found_before, found_after, own_before, own_after = [], [], [], []
        for seed in range(seeds):
            # Seeded on purpose: the same likes on every run.
            picker = random.Random(seed)  # noqa: S311
            liked = set(picker.sample(foreign, min(likes, len(foreign))))
            rest = set(world.articles) - liked
            after = ids(await rank(world, declared, signals_for(world, liked, set()), weights))
            target = set(foreign) - liked
            found_before.append(len(target & set([i for i in before if i in rest][:WIDE])))
            found_after.append(len(target & set([i for i in after if i in rest][:WIDE])))
            own_before.append(quality(before, reader, rest)[0])
            own_after.append(quality(after, reader, rest)[0])
        lines.append(
            f"| {reader.persona.key} | {other.persona.key} | {likes} "
            f"| {len(foreign) - likes} | {np.mean(found_before):.1f} | {np.mean(found_after):.1f} "
            f"| {np.mean(own_before):.3f} | {np.mean(own_after):.3f} |"
        )
    return lines


def _variety(world: World, order: list[int]) -> tuple[float, int]:
    """Mean pairwise cosine and the number of sources in the first TOP places."""
    head = [world.vectors[i] for i in order[:TOP] if i in world.vectors]
    matrix = np.stack(head)
    pairs = matrix @ matrix.T
    count = len(head)
    similarity = float((pairs.sum() - count) / (count * (count - 1)))
    return similarity, len({world.articles[i].source_id for i in order[:TOP]})


async def variety(world: World, reader: Reader, weights: Weights) -> list[str]:
    ranked = await rank(world, (*reader.interests, reader.resume), [], weights)
    plain = ids(ranked)
    sources = {article_id: article.source_id for article_id, article in world.articles.items()}
    reranked = ids(
        rerank_for_variety(
            [item for item in ranked if item.score >= weights.min_score][:240],
            world.vectors,
            sources,
            duplicate_threshold=world.embedder.duplicate_threshold,
            variety=weights.variety,
            limit=120,
        )
    )
    lines = []
    for name, order in (("по релевантности", plain), ("с перестановкой", reranked)):
        score, precision, _ = quality(order, reader, set(world.articles))
        similarity, distinct = _variety(world, order)
        lines.append(
            f"| {reader.persona.key} | {name} | {score:.3f} | {precision:.2f} "
            f"| {similarity:.3f} | {distinct} |"
        )
    return lines


async def objective(world: World, readers: list[Reader], weights: Weights) -> float:
    """What tuning maximises: cold-start quality plus quality after one screen."""
    total = 0.0
    for reader in readers:
        declared = (*reader.interests, reader.resume)
        before = ids(await rank(world, declared, [], weights))
        total += quality(before, reader, set(world.articles))[0]
        learned = 0.0
        for shown in SCREENS:
            screen = before[:shown]
            liked = {i for i in screen if reader.grades.get(i, 0) >= RELEVANT_FROM}
            disliked = {i for i in screen if reader.grades.get(i, 0) == 0}
            after = ids(await rank(world, declared, signals_for(world, liked, disliked), weights))
            learned += quality(after, reader, set(world.articles) - set(screen))[0]
        total += learned / len(SCREENS)
    return total / (2 * len(readers))


async def tune(world: World, reader: Reader) -> Weights:
    """Coarse grid over the blend, on one reader only; the other is the check."""
    best, best_value = Weights(), await objective(world, [reader], Weights())
    # The interest weight is the unit the others are measured in, so it stays.
    grid = itertools.product(
        (0.1, 0.2, 0.3, 0.45), (0.25, 0.35, 0.45, 0.6), (0.3, 0.5, 0.7, 0.9), (0.2, 0.35, 0.5)
    )
    for resume, learned, peak, avoid in grid:
        candidate = replace(Weights(), resume=resume, learned=learned, peak=peak, avoid=avoid)
        value = await objective(world, [reader], candidate)
        if value > best_value + 1e-9:
            best, best_value = candidate, value
    print(f"tuned on {reader.persona.key}: {best} -> {best_value:.4f}", flush=True)
    return best


async def main(args: argparse.Namespace) -> None:
    end = datetime.fromisoformat(args.end) if args.end else datetime.now(UTC)
    start = end - timedelta(days=args.days)
    out = Path(args.out)
    embedder = build_embedder(args.embedding)
    await embed_pending(embedder, since=start, until=end, max_articles=100_000)
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

    weights = await tune(world, readers[0]) if args.tune else Weights()
    if args.tune:
        default = await objective(world, [readers[1]], Weights())
        tuned = await objective(world, [readers[1]], weights)
        print(f"check on {readers[1].persona.key}: default {default:.4f}, tuned {tuned:.4f}")

    report = [
        f"Период: {start:%d.%m.%Y} - {end:%d.%m.%Y}, статей: {len(articles)}. Эмбеддер: "
        f"{embedder.model_id}. Эталон: оценки модели {args.judge}, релевантной считается "
        f"статья с оценкой не ниже {RELEVANT_FROM}.",
        "",
        "Релевантных статей: "
        + ", ".join(f"{reader.persona.key} - {len(reader.relevant)}" for reader in readers)
        + ".",
        "",
        "## Лента до первых оценок",
        "",
        f"| Читатель | Что известно о читателе | nDCG@{TOP} | Precision@{HEAD} | Recall@{WIDE} |",
        "|---|---|---|---|---|",
    ]
    for reader in readers:
        report += await cold_start(world, reader, weights)
    report += [
        "",
        "## Обучение на оценках",
        "",
        "Читатель оценивает первый экран: ставит лайк релевантным статьям и дизлайк статьям с "
        "оценкой 0. Качество считается по остальным статьям периода, до оценок и после.",
        "",
        f"| Читатель | Что известно | Показано | Лайков / дизлайков | nDCG@{TOP} до "
        f"| nDCG@{TOP} после | P@{HEAD} до | P@{HEAD} после |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for reader in readers:
        report += await learning(world, reader, weights)
    report += [
        "",
        "## Интерес, которого нет в профиле",
        "",
        "Читатель с одним профилем лайкает несколько статей из чужой области. Сколько остальных "
        f"статей этой области попадает в первые {WIDE} мест ленты и что происходит с качеством по "
        "его собственному профилю. Среднее по пяти случайным наборам лайков.",
        "",
        f"| Профиль читателя | Область лайков | Лайков | Осталось найти | В топ-{WIDE} до "
        f"| В топ-{WIDE} после | Свой nDCG@{TOP} до | после |",
        "|---|---|---|---|---|---|---|---|",
    ]
    report += await hidden_interest(world, readers[0], readers[1], weights)
    report += await hidden_interest(world, readers[1], readers[0], weights)
    report += [
        "",
        "## Перестановка ради разнообразия",
        "",
        f"| Читатель | Порядок | nDCG@{TOP} | Precision@{HEAD} | Средняя близость пар в топ-{TOP} "
        f"| Источников в топ-{TOP} |",
        "|---|---|---|---|---|---|",
    ]
    for reader in readers:
        report += await variety(world, reader, weights)
    text = "\n".join(report) + "\n"
    (out / "recsys.md").write_text(text, "utf-8")
    (out / "recsys-weights.json").write_text(
        json.dumps(
            {name: getattr(weights, name) for name in Weights.__dataclass_fields__}, indent=2
        ),
        "utf-8",
    )
    print(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--end", default=None, help="End of the period, ISO 8601; now if omitted.")
    parser.add_argument("--judge", default="qwen3.5:9b")
    parser.add_argument("--embedding", default="embeddinggemma:300m")
    parser.add_argument("--tune", action="store_true", help="Search the blend weights first.")
    parser.add_argument("--out", default="../docs/eval")
    aio.run(main(parser.parse_args()))
