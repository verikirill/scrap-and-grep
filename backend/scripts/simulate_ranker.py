"""Run the learned ranker's whole path on simulated readers.

    uv run python scripts/simulate_ranker.py --end 2026-09-30T18:00:00+00:00 --readers 40 200

The stand has no live traffic, so readers are simulated on the week of
articles the feed was measured on (scripts/eval_recsys.py), with the same
reference: the language model's grade of every article for each of the two
profiles. Simulated readers get a feed list every day for two weeks, ranked
by the hand blend. They look down the list less and less often the lower an
article is, and open, like, save or dislike it with chances that depend on
its grade. Everything they do goes the real way: events into the Valkey
stream, the writer into ClickHouse (a database of its own, radar_sim), the
training query back out of it, LightGBM, and the same comparison that
decides whether a model is switched on. Nothing is stored in PostgreSQL.

Articles are split in two halves: training days show one half, the last
days the other, as new articles arrive in real life. Without the split the
model would recognise articles it had seen and win for the wrong reason.

The behaviour is a model of readers, not readers. The numbers say whether
the path works and what it can learn from such data; only live traffic says
what it gains.
"""

import argparse
import asyncio
import json
import math
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

# Before radar reads its settings: events go to a database and a Valkey db of
# their own, never to the running stack's.
os.environ.setdefault("RADAR_CLICKHOUSE_URL", "http://127.0.0.1:8123")
os.environ.setdefault("RADAR_CLICKHOUSE_USER", "radar")
os.environ.setdefault("RADAR_CLICKHOUSE_PASSWORD", "radar")
os.environ["RADAR_CLICKHOUSE_DATABASE"] = "radar_sim"
os.environ["RADAR_CACHE_URL"] = "redis://127.0.0.1:6379/14"

from eval_recsys import PERSONAS, World, build_embedder, build_reader, rank
from eval_retrieval import load_articles

from radar import aio
from radar.cache import get_redis
from radar.db import session_scope
from radar.db.models import Article
from radar.events import clickhouse, emit
from radar.events.model import Event
from radar.events.writer import flush
from radar.ingest.service import embed_pending
from radar.ranker.features import FEATURES, served
from radar.ranker.train import evaluate, fit, holdout_from, load, ndcg
from radar.recsys import store
from radar.recsys.ranking import Ranked, Weights
from radar.store.articles import load_vectors

# The report's account of the method, for readers of docs/eval.
METHOD = """
Живого трафика на стенде нет, поэтому читатели смоделированы на той же неделе статей, на
которой мерили ленту (scripts/eval_recsys.py), и с тем же эталоном: оценкой модели-судьи для
каждого из двух профилей. Две недели каждый читатель получает в день список из 30 статей в
порядке ручных весов. Чем ниже статья, тем реже он до неё доходит: место p он видит с
вероятностью 1/p^0,6. Открывает, лайкает, сохраняет или дизлайкает с шансами, которые
зависят от оценки статьи. Всё идёт настоящим путём: события в поток Valkey, писатель в
ClickHouse (своя база radar_sim), обучающий запрос обратно, LightGBM и то же сравнение,
которым ночное обучение решает, включать ли модель. В PostgreSQL ничего не пишется.

Статьи поделены пополам: дни обучения показывают одну половину, дни проверки другую, как в
жизни каждый день приходят новые статьи. Иначе модель узнавала бы уже виденные статьи и
выигрывала бы не за то.

Поведение здесь смоделировано, это не живые читатели. Цифры показывают, что путь работает и
чему модель может научиться из таких данных. Сколько она даёт на деле, покажет только живой
трафик.
"""

SIM_DAYS = 14
LIST_SIZE = 30
CANDIDATES = 150
DEPTH = 20
# Chance that a reader looks at the article in place p: 1 / p^0.6, so the
# tenth place is looked at a quarter as often as the first.
LOOK_DECAY = 0.6
# Chances by grade (0-3) once the article is looked at.
OPEN = (0.02, 0.08, 0.35, 0.6)
LIKE = (0.05, 0.15, 0.45, 0.65)
SAVE = 0.2
DISLIKE = (0.1, 0.02, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class Persona:
    key: str
    grades: dict[int, int]
    # Article id -> what the hand blend says about it for this persona.
    ranked: dict[int, Ranked]


def stored_grades(path: Path, articles: list[Article]) -> dict[int, int]:
    """The reference grades as the feed measurements stored them, by article id.
    Articles published since are left out: nothing is graded anew here."""
    by_url = json.loads(path.read_text("utf-8"))["grades"]
    return {article.id: by_url[article.url] for article in articles if article.url in by_url}


def look(position: int) -> float:
    return float(position**-LOOK_DECAY)


def events_for_list(
    rng: np.random.Generator,
    reader: uuid.UUID,
    persona: Persona,
    articles: list[int],
    served_at: datetime,
) -> list[Event]:
    snapshot = uuid.uuid4()
    order = sorted(articles, key=lambda article: -persona.ranked[article].score)[:LIST_SIZE]
    events = []
    for position, article in enumerate(order, start=1):
        item = persona.ranked[article]
        placed = {"surface": "feed", "article_id": article, "request_id": snapshot}
        events.append(
            Event(
                "served",
                reader,
                ts=served_at,
                position=position,
                slot="ranked",
                score=item.score,
                features=served(item.parts, item.score, 0.0),
                variant="hand",
                **placed,
            )
        )
        if rng.random() > look(position):
            continue
        grade = persona.grades.get(article, 0)
        at = served_at + timedelta(seconds=10 * position)
        events.append(Event("impression", reader, ts=at, position=position, **placed))
        if rng.random() < DISLIKE[grade]:
            events.append(Event("dislike", reader, ts=at, position=position, **placed))
        elif rng.random() < OPEN[grade]:
            events.append(Event("open", reader, ts=at, position=position, **placed))
            if rng.random() < LIKE[grade]:
                events.append(Event("like", reader, ts=at, position=position, **placed))
                if rng.random() < SAVE:
                    events.append(Event("save", reader, ts=at, position=position, **placed))
    return events


def ndcg_by_grade(order: list[int], grades: dict[int, int]) -> float:
    return ndcg(np.array([grades.get(article, 0) for article in order], dtype=float), DEPTH)


def ranked_by_model(booster: object, persona: Persona, articles: list[int]) -> list[int]:
    rows = [served(persona.ranked[a].parts, persona.ranked[a].score, 0.0) for a in articles]
    matrix = np.array([[row.get(name, 0.0) for name in FEATURES] for row in rows])
    predicted = booster.predict(matrix, num_threads=1)  # type: ignore[attr-defined]
    return [articles[int(index)] for index in np.argsort(-predicted, kind="stable")]


@dataclass(frozen=True, slots=True)
class Run:
    readers: int
    train_lists: int
    holdout_lists: int
    actions: int
    hand: float
    model: float
    decision: str
    # Profile -> nDCG@20 against the grades: hand blend, model, model without
    # the correction for places.
    by_grade: dict[str, tuple[float, float, float]]


async def world_and_personas(args: argparse.Namespace) -> tuple[World, list[Persona]]:
    end = datetime.fromisoformat(args.end)
    start = end - timedelta(days=7)
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
    personas = []
    for persona in PERSONAS:
        grades = stored_grades(Path(args.grades) / persona.grades_file, articles)
        reader = await build_reader(persona, world, grades)
        declared = (*reader.interests, reader.resume)
        ranked = await rank(world, declared, [], Weights())
        personas.append(Persona(persona.key, grades, {item.article_id: item for item in ranked}))
    return world, personas


async def simulate(
    count: int, personas: list[Persona], halves: tuple[list[int], list[int]], seed: int
) -> Run:
    """Two weeks of `count` readers through the real path, then the nightly comparison."""
    rng = np.random.default_rng(seed)
    seen_half, new_half = halves
    async with clickhouse.connect(database="default") as client:
        await client.command("DROP DATABASE IF EXISTS radar_sim")
    await clickhouse.migrate()
    await get_redis().flushdb()

    now = datetime.now(UTC).replace(microsecond=0)
    first_day = now - timedelta(days=SIM_DAYS)
    readers = [(uuid.uuid4(), personas[index % len(personas)]) for index in range(count)]
    held_from = holdout_from(now)
    for day in range(SIM_DAYS):
        moment = first_day + timedelta(days=day)
        pool = new_half if moment >= held_from else seen_half
        for index, (reader, persona) in enumerate(readers):
            served_at = moment + timedelta(seconds=30 * index)
            sample = [int(a) for a in rng.choice(pool, size=CANDIDATES, replace=False)]
            await emit(*events_for_list(rng, reader, persona, sample, served_at))
    while await flush(budget_seconds=120):
        pass

    lists = await load(now - timedelta(days=SIM_DAYS + 1), now)
    outcome = await asyncio.to_thread(evaluate, lists, now)
    train = lists.take([moment < held_from for moment in lists.served_at])
    naive = await asyncio.to_thread(fit, train, debias=False)
    by_grade = {}
    for persona in personas:
        by_hand = sorted(new_half, key=lambda article: -persona.ranked[article].score)
        by_grade[persona.key] = (
            ndcg_by_grade(by_hand, persona.grades),
            ndcg_by_grade(ranked_by_model(outcome.booster, persona, new_half), persona.grades)
            if outcome.booster
            else math.nan,
            ndcg_by_grade(ranked_by_model(naive, persona, new_half), persona.grades),
        )
    metrics = outcome.metrics
    return Run(
        readers=count,
        train_lists=int(metrics.get("train_lists", 0)),
        holdout_lists=int(metrics.get("holdout_lists", 0)),
        actions=int(metrics.get("actions", 0)),
        hand=metrics.get("hand_ndcg", math.nan),
        model=metrics.get("model_ndcg", math.nan),
        decision=outcome.note,
        by_grade=by_grade,
    )


def report(runs: list[Run], articles: int, seed: int, embedder: str) -> list[str]:
    lines = [
        f"Статей недели с оценками: {articles}, по половине на обучение и проверку. "
        f"Читатели поровну на два профиля, {SIM_DAYS} дней по одному списку из {LIST_SIZE} "
        f"статей в день. Эмбеддер {embedder}, зерно {seed}.",
        "",
        "## Проверка на последних днях, по кликам читателей",
        "",
        "Ровно то сравнение, которым ночное обучение решает, включать ли модель.",
        "",
        "| Читателей | Списков: обучение / проверка | Открытий и отметок | nDCG@20 ручные веса "
        "| nDCG@20 модель | Решение |",
        "|---|---|---|---|---|---|",
    ]
    for run in runs:
        lines.append(
            f"| {run.readers} | {run.train_lists} / {run.holdout_lists} | {run.actions} "
            f"| {run.hand:.3f} | {run.model:.3f} | {run.decision} |"
        )
    lines += [
        "",
        "## По эталонным оценкам, на статьях, которых модель не видела",
        "",
        "Все статьи второй половины, упорядоченные целиком, против оценок модели-судьи (0-3).",
        "",
        "| Читателей | Профиль | Ручные веса | Модель | Модель без поправки на место |",
        "|---|---|---|---|---|",
    ]
    for run in runs:
        for key, values in run.by_grade.items():
            cells = " | ".join(f"{value:.3f}" for value in values)
            lines.append(f"| {run.readers} | {key} | {cells} |")
    return lines


async def main(args: argparse.Namespace) -> None:
    world, personas = await world_and_personas(args)
    # Articles both profiles have a score and a grade for, in two halves.
    ids = sorted(
        set(world.articles).intersection(
            *(persona.ranked for persona in personas), *(persona.grades for persona in personas)
        )
    )
    np.random.default_rng(args.seed).shuffle(ids)
    halves = (ids[: len(ids) // 2], ids[len(ids) // 2 :])
    runs = [await simulate(count, personas, halves, args.seed) for count in args.readers]
    lines = report(runs, len(ids), args.seed, world.embedder.model_id)
    # Paragraphs are wrapped here for the source and on one line in the report.
    method = [" ".join(paragraph.split()) for paragraph in METHOD.strip().split("\n\n")]
    header = ["# Обучаемое ранжирование на симуляции", "", "\n\n".join(method), ""]
    path = Path(args.out) / "ranker.md"
    path.write_text("\n".join([*header, *lines, ""]), encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--end", required=True, help="End of the measured week, ISO 8601.")
    parser.add_argument("--grades", default="../docs/eval", help="Where the grade files are.")
    parser.add_argument("--embedding", default="embeddinggemma:300m")
    parser.add_argument("--readers", type=int, nargs="+", default=[40, 200])
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default="../docs/eval")
    aio.run(main(parser.parse_args()))
