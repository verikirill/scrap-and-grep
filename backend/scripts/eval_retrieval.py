"""Compare retrieval variants on the project's own articles.

    uv run python scripts/eval_retrieval.py --days 7 --out ../docs/eval

Question: which embedder, and which way of combining it with full-text
search, brings the articles a reader would want into the candidate pool?

Method. Every article of the period is graded for one profile by the language
model (0-3, the same prompt the pipeline uses). These grades are the reference:
"relevant" means grade >= 2. Each retrieval variant then ranks the same
articles, and we measure how much of the relevant set it puts into the top-K
that the pipeline would pass on to grading.

The reference is a model's judgement, not a human's, and it comes from the same
model the pipeline uses downstream. The numbers therefore say how well a
retriever feeds this pipeline, not how well it matches an expert. Grades are
cached in a JSON file, so re-runs are cheap and the labels can be inspected.

A later run over the same grades, on a database that has grown since:

    uv run python scripts/eval_retrieval.py --until 2026-09-30T16:00:00+00:00 \
        --graded-only --embedding embeddinggemma:300m \
        --openai text-embeddings-v2-doc/latest:text-embeddings-v2-query/latest@768

`--openai` takes DOC[:QUERY][@WIDTH] and asks the server of
RADAR_EMBEDDING_BASE_URL with RADAR_EMBEDDING_API_KEY; with
RADAR_EMBEDDING_PROJECT set a bare name becomes Yandex's emb://<folder>/<name>.
"""

import argparse
import asyncio
import json
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from radar import aio
from radar.ai.embedder import (
    Embedder,
    HashingEmbedder,
    OllamaEmbedder,
    OpenAIEmbedder,
    short_model_name,
)
from radar.ai.factory import embedding_preset
from radar.ai.llm import ModelIntelligence, ollama_chat
from radar.ai.prompts import PROMPT_VERSION
from radar.config import get_settings
from radar.db import session_scope
from radar.db.models import Article, Profile
from radar.domain import Candidate, ProfileSpec
from radar.ingest.service import embed_pending
from radar.selection.retrieval import Window, keyword_query, search
from radar.store.articles import to_ref

TOP_K = 60
WIDE_K = 120
HEAD_K = 20
RELEVANT_FROM = 2


@dataclass(frozen=True, slots=True)
class Row:
    embedder: str
    ranking: str
    recall: float
    recall_wide: float
    precision_head: float
    ndcg: float


async def load_articles(start: datetime, end: datetime) -> list[Article]:
    async with session_scope() as session:
        result = await session.execute(
            select(Article).where(Article.published_at >= start, Article.published_at < end)
        )
        return list(result.scalars().all())


async def grade_all(
    articles: list[Article], profile: ProfileSpec, cache_path: Path, model: str
) -> dict[int, int]:
    """Grade every article with the language model; cached on disk by URL.

    The cache remembers what produced it. Grades made for another profile, by
    another model or with another prompt are not a reference for this run.
    """
    origin = {"profile": profile.fingerprint(), "judge": model, "prompt": PROMPT_VERSION}
    stored = json.loads(cache_path.read_text("utf-8")) if cache_path.exists() else {}
    if stored and stored.get("origin") != origin:
        raise SystemExit(f"{cache_path} was made with {stored.get('origin')}; move it away first")
    cached: dict[str, int] = stored.get("grades", {})
    settings = get_settings()
    judge = ModelIntelligence(
        ollama_chat(model, settings.ollama_base_url, temperature=0.0, concurrency=4)
    )
    todo = [article for article in articles if article.url not in cached]
    print(f"grading {len(todo)} articles with {model} ({len(cached)} cached)", flush=True)

    async def one(article: Article) -> None:
        candidate = Candidate(article=to_ref(article), interest_id=profile.interests[0].id)
        try:
            cached[article.url] = (await judge.grade(candidate, profile)).relevance
        except Exception as exc:
            print(f"  grade failed for {article.id}: {type(exc).__name__}", flush=True)

    for start in range(0, len(todo), 40):
        await asyncio.gather(*(one(article) for article in todo[start : start + 40]))
        payload = {"origin": origin, "grades": cached}
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=0), "utf-8")
        print(f"  {min(start + 40, len(todo))}/{len(todo)}", flush=True)
    ungraded = [article.id for article in articles if article.url not in cached]
    if ungraded:
        # An ungraded article would count as irrelevant and flatter every ranking.
        raise SystemExit(f"{len(ungraded)} articles have no grade; run again to retry them")
    return {article.id: cached[article.url] for article in articles}


def metrics(ranked: list[int], grades: dict[int, int]) -> tuple[float, float, float, float]:
    relevant = {article_id for article_id, grade in grades.items() if grade >= RELEVANT_FROM}
    top = ranked[:TOP_K]
    recall = len(relevant & set(top)) / len(relevant) if relevant else 0.0
    wide = len(relevant & set(ranked[:WIDE_K])) / len(relevant) if relevant else 0.0
    head = ranked[:HEAD_K]
    precision = sum(1 for article_id in head if article_id in relevant) / HEAD_K
    gain = sum(
        (2 ** grades.get(article_id, 0) - 1) / math.log2(position + 2)
        for position, article_id in enumerate(top)
    )
    ideal = sum(
        (2**grade - 1) / math.log2(position + 2)
        for position, grade in enumerate(sorted(grades.values(), reverse=True)[:TOP_K])
    )
    return recall, wide, precision, gain / ideal if ideal else 0.0


@dataclass(frozen=True, slots=True)
class Cost:
    embedder: str
    articles: int
    seconds: float
    # Requests to the server where the embedder counts them (OpenAI-compatible).
    requests: int | None


async def evaluate(
    embedder: Embedder,
    profile: ProfileSpec,
    window: Window,
    grades: dict[int, int],
    *,
    graded_only: bool = False,
) -> tuple[list[Row], Cost]:
    began = time.perf_counter()
    embedded = await embed_pending(
        embedder, since=window.start, until=window.end, max_articles=100_000
    )
    vectors = await embedder.embed([interest.as_query() for interest in profile.interests], "query")
    cost = Cost(
        embedder.model_id,
        embedded,
        time.perf_counter() - began,
        embedder.requests if isinstance(embedder, OpenAIEmbedder) else None,
    )
    dense: dict[int, float] = {}
    lexical: dict[int, float] = {}
    combined: dict[int, float] = {}
    async with session_scope() as session:
        for interest, vector in zip(profile.interests, vectors, strict=True):
            hits = await search(
                session,
                model=embedder.model_id,
                window=window,
                query_vector=vector,
                query_text=keyword_query(interest.keywords or (interest.title,)),
                limit=100_000,
                semantic=embedder.semantic,
            )
            for hit in hits:
                dense[hit.article_id] = max(dense.get(hit.article_id, -99.0), hit.z_score)
                if hit.lexical_hit:
                    lexical[hit.article_id] = max(lexical.get(hit.article_id, 0.0), hit.rank_share)
                combined[hit.article_id] = max(combined.get(hit.article_id, 0.0), hit.score)

    def rank(scores: dict[int, float]) -> list[int]:
        # Over grades made earlier, articles that came in since have no grade
        # and would take places as irrelevant ones: they are left out.
        ids = [article_id for article_id in scores if not graded_only or article_id in grades]
        return sorted(ids, key=lambda article_id: (-scores[article_id], article_id))

    rows = []
    for name, scores in (
        ("только векторы", dense),
        ("только полнотекстовый", lexical),
        ("как в конвейере", combined),
    ):
        recall, wide, precision, ndcg = metrics(rank(scores), grades)
        rows.append(Row(embedder.model_id, name, recall, wide, precision, ndcg))
    return rows, cost


def openai_embedder(spec: str) -> OpenAIEmbedder:
    """DOC[:QUERY][@WIDTH] on the server of the settings."""
    settings = get_settings()
    names, _, width = spec.partition("@")
    document, _, query = names.partition(":")

    def uri(name: str) -> str:
        project = settings.embedding_project
        return f"emb://{project}/{name}" if name and project and "://" not in name else name

    preset = embedding_preset(short_model_name(document))
    key = settings.embedding_api_key
    return OpenAIEmbedder(
        uri(document),
        settings.embedding_base_url,
        query_model=uri(query),
        api_key=key.get_secret_value() if key else None,
        project=settings.embedding_project,
        dimensions=int(width) if width else preset.dimensions,
        requests_per_second=settings.embedding_requests_per_second,
    )


def build_embedders(models: list[str], openai: list[str]) -> list[Embedder]:
    """ "hashing" among the models is the offline stand-in, the rest are Ollama's."""
    settings = get_settings()
    embedders: list[Embedder] = []
    for model in models:
        if model == "hashing":
            embedders.append(HashingEmbedder())
            continue
        preset = embedding_preset(model)
        embedders.append(
            OllamaEmbedder(
                model,
                settings.ollama_base_url,
                query_prefix=preset.query_prefix,
                document_prefix=preset.document_prefix,
                dimensions=preset.dimensions,
            )
        )
    embedders.extend(openai_embedder(spec) for spec in openai)
    return embedders


async def load_profile(name: str, grades_path: Path) -> ProfileSpec:
    """The profile of that name; of several, the one the cached grades were made for."""
    origin = (
        json.loads(grades_path.read_text("utf-8")).get("origin", {}) if grades_path.exists() else {}
    )
    async with session_scope() as session:
        stored = (await session.scalars(select(Profile).where(Profile.name == name))).all()
    specs = [ProfileSpec.model_validate(profile.spec) for profile in stored]
    if not specs:
        raise SystemExit(f"unknown profile: {name}")
    return next((spec for spec in specs if spec.fingerprint() == origin.get("profile")), specs[0])


async def cached_grades(
    grades_path: Path, profile: ProfileSpec, start: datetime, end: datetime
) -> dict[int, int]:
    """The grades the cache has for the articles of the window, nothing graded anew.

    The prompt may have changed since: the labels stay those of the cache, and
    they still say what this profile wants. Grades of another profile do not.
    """
    stored = json.loads(grades_path.read_text("utf-8"))
    if stored["origin"]["profile"] != profile.fingerprint():
        raise SystemExit(f"{grades_path} was made for another version of {profile.name}")
    cached: dict[str, int] = stored["grades"]
    articles = await load_articles(start, end)
    return {article.id: cached[article.url] for article in articles if article.url in cached}


async def main(args: argparse.Namespace) -> None:
    end = datetime.fromisoformat(args.until) if args.until else datetime.now(UTC)
    start = end - timedelta(days=args.days)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    grades_path = Path(args.grades) if args.grades else out / "grades.json"
    profile = await load_profile(args.profile, grades_path)
    window = Window(start=start, end=end, languages=profile.languages, categories=())

    grades = (
        await cached_grades(grades_path, profile, start, end)
        if args.graded_only
        else await grade_all(await load_articles(start, end), profile, grades_path, args.judge)
    )
    relevant = sum(1 for grade in grades.values() if grade >= RELEVANT_FROM)

    rows: list[Row] = []
    costs: list[Cost] = []
    for embedder in build_embedders(args.embedding, args.openai):
        print(f"evaluating {embedder.model_id}", flush=True)
        found, cost = await evaluate(
            embedder, profile, window, grades, graded_only=args.graded_only
        )
        rows.extend(found)
        costs.append(cost)

    lines = [
        f"Профиль: {profile.name}. Период: {args.days} дн., статей: {len(grades)}, "
        f"релевантных (оценка модели {args.judge} не ниже {RELEVANT_FROM}): {relevant}.",
        "",
        f"| Эмбеддер | Ранжирование | Recall@{TOP_K} | Recall@{WIDE_K} | Precision@{HEAD_K} "
        f"| nDCG@{TOP_K} |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {row.embedder} | {row.ranking} | {row.recall:.3f} | {row.recall_wide:.3f} "
        f"| {row.precision_head:.3f} | {row.ndcg:.3f} |"
        for row in rows
    ]
    lines += [
        "",
        "| Эмбеддер | Новых векторов | Время, с | Запросов |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {cost.embedder} | {cost.articles} | {cost.seconds:.1f} "
        f"| {'-' if cost.requests is None else cost.requests} |"
        for cost in costs
    ]
    report = "\n".join(lines) + "\n"
    (out / args.report).write_text(report, "utf-8")
    print(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--until", help="end of the window, ISO 8601; now by default")
    parser.add_argument("--profile", default="Специалист по ИБ АСУ ТП")
    parser.add_argument("--judge", default="qwen3.5:9b")
    parser.add_argument(
        "--embedding", nargs="*", default=["hashing", "bge-m3", "qwen3-embedding:4b"]
    )
    parser.add_argument("--openai", nargs="*", default=[], help="DOC[:QUERY][@WIDTH]")
    parser.add_argument("--grades", help="the grade cache; <out>/grades.json by default")
    parser.add_argument(
        "--graded-only",
        action="store_true",
        help="rank only the articles the cache has grades for, whatever prompt made them",
    )
    parser.add_argument("--out", default="../docs/eval")
    parser.add_argument("--report", default="retrieval.md")
    aio.run(main(parser.parse_args()))
