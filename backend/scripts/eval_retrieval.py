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
"""

import argparse
import asyncio
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from radar import aio
from radar.ai.embedder import Embedder, HashingEmbedder, OllamaEmbedder
from radar.ai.factory import embedding_preset
from radar.ai.ollama import OllamaIntelligence
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
    """Grade every article with the language model; cached on disk by URL."""
    cached: dict[str, int] = (
        json.loads(cache_path.read_text("utf-8")) if cache_path.exists() else {}
    )
    settings = get_settings()
    judge = OllamaIntelligence(model, settings.ollama_base_url, temperature=0.0, concurrency=4)
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
        cache_path.write_text(json.dumps(cached, ensure_ascii=False, indent=0), "utf-8")
        print(f"  {min(start + 40, len(todo))}/{len(todo)}", flush=True)
    return {article.id: cached[article.url] for article in articles if article.url in cached}


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


async def evaluate(
    embedder: Embedder, profile: ProfileSpec, window: Window, grades: dict[int, int]
) -> list[Row]:
    await embed_pending(embedder, since=window.start, until=window.end, max_articles=100_000)
    vectors = await embedder.embed([interest.as_query() for interest in profile.interests], "query")
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
        return sorted(scores, key=lambda article_id: (-scores[article_id], article_id))

    rows = []
    for name, scores in (
        ("только векторы", dense),
        ("только полнотекстовый", lexical),
        ("как в конвейере", combined),
    ):
        recall, wide, precision, ndcg = metrics(rank(scores), grades)
        rows.append(Row(embedder.model_id, name, recall, wide, precision, ndcg))
    return rows


def build_embedders(models: list[str]) -> list[Embedder]:
    settings = get_settings()
    embedders: list[Embedder] = [HashingEmbedder()]
    for model in models:
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
    return embedders


async def main(args: argparse.Namespace) -> None:
    end = datetime.now(UTC)
    start = end - timedelta(days=args.days)
    async with session_scope() as session:
        stored = await session.scalar(select(Profile).where(Profile.name == args.profile))
    if stored is None:
        raise SystemExit(f"unknown profile: {args.profile}")
    profile = ProfileSpec.model_validate(stored.spec)
    window = Window(start=start, end=end, languages=profile.languages, categories=())

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    articles = await load_articles(start, end)
    grades = await grade_all(articles, profile, out / "grades.json", args.judge)
    relevant = sum(1 for grade in grades.values() if grade >= RELEVANT_FROM)

    rows: list[Row] = []
    for embedder in build_embedders(args.embedding):
        print(f"evaluating {embedder.model_id}", flush=True)
        rows.extend(await evaluate(embedder, profile, window, grades))

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
    report = "\n".join(lines) + "\n"
    (out / "retrieval.md").write_text(report, "utf-8")
    print(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--profile", default="Специалист по ИБ АСУ ТП")
    parser.add_argument("--judge", default="qwen3.5:9b")
    parser.add_argument("--embedding", nargs="*", default=["bge-m3", "qwen3-embedding:4b"])
    parser.add_argument("--out", default="../docs/eval")
    aio.run(main(parser.parse_args()))
