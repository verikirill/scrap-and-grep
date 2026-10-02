"""Database side of the recommender: signals, evidence, readers alike."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.config import EMBEDDING_DIM
from radar.db.models import Article, ArticleEmbedding, Impression, Interaction, UserVector
from radar.recsys.ranking import Evidence
from radar.recsys.signals import KIND_OPEN, KIND_SAVE, OPPOSITE, REJECTING
from radar.recsys.taste import Facet, Signal

# The newest signals are enough: older ones have decayed to a fraction.
# Opened links are counted apart, so that a reader who opens a lot does not
# push their deliberate likes and hides out of the window.
SIGNAL_LIMIT = 200
OPEN_LIMIT = 100
# Seen articles an adaptation looks at, newest first.
SEEN_LIMIT = 500
# A reader alike must be this close on centred taste vectors (0 is "unrelated").
COLLAB_MIN_SIMILARITY = 0.3
COLLAB_NEIGHBOURS = 20
COLLAB_DAYS = 30
# An article is reported as "liked by colleagues" only when at least this
# many of them did. With one or two, a reader with a second account could
# work out what a particular colleague reads.
COLLAB_MIN_READERS = 3

# One pass over the period for all facets at once. Every article of the period
# gets a similarity to every facet, which yields the mean and deviation for
# the z-score; then only the pool of plausible candidates is returned. The
# result is three kinds of rows: similarities, full-text ranks and metadata.
_EVIDENCE_SQL = """
    WITH scope AS (
        SELECT a.id, a.source_id, a.published_at, a.search_tsv, e.embedding
        FROM articles a
        LEFT JOIN article_embeddings e ON e.article_id = a.id AND e.model = :model
        WHERE a.published_at >= :start AND a.published_at < :end
          AND a.language = ANY(CAST(:languages AS text[]))
          AND a.id <> ALL(CAST(:skip AS bigint[]))
          AND NOT EXISTS (
              SELECT 1 FROM unnest(CAST(:exclusions AS text[])) AS x(query)
              WHERE a.search_tsv @@ websearch_to_tsquery('russian', x.query)
          )
    ),
    facets AS (
        SELECT key, CAST(vec AS vector) AS vec, has_vec, query, positive
        FROM unnest(
            CAST(:keys AS text[]), CAST(:vecs AS text[]), CAST(:has_vecs AS boolean[]),
            CAST(:queries AS text[]), CAST(:positive AS boolean[])
        ) AS f(key, vec, has_vec, query, positive)
    ),
    sims AS (
        SELECT f.key, f.positive, s.id, 1 - (s.embedding <=> f.vec) AS sim
        FROM scope s CROSS JOIN facets f
        -- A zero vector has no direction; its cosine is NaN and would poison
        -- the statistics of the whole facet.
        WHERE f.has_vec AND s.embedding IS NOT NULL AND vector_norm(s.embedding) > 0
    ),
    scored AS (
        SELECT key, positive, id,
               (sim - avg(sim) OVER facet) / NULLIF(stddev_pop(sim) OVER facet, 0) AS z,
               row_number() OVER (PARTITION BY key ORDER BY sim DESC) AS place
        FROM sims
        WINDOW facet AS (PARTITION BY key)
    ),
    lexical AS (
        SELECT f.key, s.id, ts_rank_cd(s.search_tsv, tsq) AS rank
        FROM facets f
        CROSS JOIN LATERAL websearch_to_tsquery('russian', f.query) AS tsq
        JOIN scope s ON s.search_tsv @@ tsq
        WHERE f.query <> ''
    ),
    lexical_ranked AS (
        SELECT key, id,
               rank / NULLIF(max(rank) OVER (PARTITION BY key), 0) AS share,
               row_number() OVER (PARTITION BY key ORDER BY rank DESC) AS place
        FROM lexical
    ),
    pool AS (
        {pool}
    )
    SELECT 'z' AS what, scored.id, scored.key, scored.z AS value
    FROM scored JOIN pool USING (id)
    UNION ALL
    SELECT 'lexical', lexical_ranked.id, lexical_ranked.key, lexical_ranked.share
    FROM lexical_ranked JOIN pool USING (id)
    UNION ALL
    SELECT 'meta', scope.id, CAST(scope.source_id AS text),
           EXTRACT(EPOCH FROM (CAST(:now AS timestamptz) - scope.published_at)) / 3600
    FROM scope JOIN pool USING (id)
"""

# Candidates for a feed: the best of every positive facet by meaning and by
# keywords, plus the newest articles as material for exploration.
_FEED_POOL = """
        SELECT id FROM scored WHERE positive AND place <= :per_facet
        UNION
        SELECT id FROM lexical_ranked WHERE place <= :per_facet
        UNION
        (SELECT id FROM scope ORDER BY published_at DESC LIMIT :fresh)
"""
# A fixed set of articles, e.g. the candidates of a digest.
_GIVEN_POOL = """
        SELECT id FROM scope WHERE id = ANY(CAST(:include AS bigint[]))
"""

_COLLAB_SQL = text(
    """
    WITH me AS (
        SELECT embedding FROM user_vectors WHERE user_id = :user_id AND model = :model
    ),
    neighbours AS (
        SELECT v.user_id, 1 - (v.embedding <=> me.embedding) AS similarity
        FROM user_vectors v
        CROSS JOIN me
        -- Guests are throwaway accounts: their clicks say nothing about
        -- what colleagues read.
        JOIN users u ON u.id = v.user_id AND NOT u.is_demo
        WHERE v.model = :model AND v.user_id <> :user_id
        ORDER BY v.embedding <=> me.embedding
        LIMIT :neighbours
    )
    SELECT i.article_id,
           sum(n.similarity * CASE i.kind WHEN 'save' THEN 1.2 ELSE 1.0 END)
               AS weight
    FROM interactions i
    JOIN neighbours n ON n.user_id = i.user_id
    WHERE n.similarity >= :min_similarity
      -- Deliberate signals only: an opened link is not a recommendation.
      AND i.kind IN ('like', 'save')
      AND i.created_at >= now() - make_interval(days => :days)
      AND i.article_id = ANY(CAST(:ids AS bigint[]))
    GROUP BY i.article_id
    HAVING count(DISTINCT i.user_id) >= :min_readers
    """
)


# The same neighbours as above, but listing what they liked instead of
# scoring given articles: material for interests the reader has not stated.
_LIKED_BY_ALIKE_SQL = text(
    """
    WITH me AS (
        SELECT embedding FROM user_vectors WHERE user_id = :user_id AND model = :model
    ),
    neighbours AS (
        SELECT v.user_id, 1 - (v.embedding <=> me.embedding) AS similarity
        FROM user_vectors v
        CROSS JOIN me
        JOIN users u ON u.id = v.user_id AND NOT u.is_demo
        WHERE v.model = :model AND v.user_id <> :user_id
        ORDER BY v.embedding <=> me.embedding
        LIMIT :neighbours
    )
    SELECT i.article_id,
           sum(n.similarity * CASE i.kind WHEN 'save' THEN 1.2 ELSE 1.0 END) AS weight
    FROM interactions i
    JOIN neighbours n ON n.user_id = i.user_id
    WHERE n.similarity >= :min_similarity
      AND i.kind IN ('like', 'save')
      AND i.created_at >= now() - make_interval(days => :days)
      -- A neighbour who liked it and later rejected it does not recommend it.
      AND NOT EXISTS (
          SELECT 1 FROM interactions r
          WHERE r.user_id = i.user_id AND r.article_id = i.article_id
            AND r.kind IN ('dislike', 'hide')
      )
    GROUP BY i.article_id
    HAVING count(DISTINCT i.user_id) >= :min_readers
    ORDER BY weight DESC
    LIMIT :limit
    """
)


@dataclass(frozen=True, slots=True)
class Scope:
    """Which articles are considered."""

    start: datetime
    end: datetime
    languages: tuple[str, ...] = ("ru", "en")
    # Full-text queries; an article matching any of them is left out.
    exclusions: tuple[str, ...] = ()
    # Articles to leave out by id, e.g. the ones the reader rejected.
    skip: tuple[int, ...] = ()


def _vector_literal(vector: np.ndarray | None) -> str:
    if vector is None:
        return "[" + ",".join(["0"] * EMBEDDING_DIM) + "]"
    return "[" + ",".join(f"{value:.6f}" for value in vector.tolist()) + "]"


async def evidence(
    session: AsyncSession,
    *,
    model: str,
    scope: Scope,
    facets: Sequence[Facet],
    per_facet: int = 40,
    fresh: int = 60,
    include: Sequence[int] | None = None,
) -> list[Evidence]:
    """Evidence for the feed pool, or for exactly the `include` articles."""
    pool = _GIVEN_POOL if include is not None else _FEED_POOL
    now = datetime.now(UTC)
    parameters: dict[str, Any] = {
        "model": model,
        "start": scope.start,
        "end": scope.end,
        "languages": list(scope.languages),
        "skip": list(scope.skip),
        "exclusions": list(scope.exclusions),
        "keys": [facet.key for facet in facets],
        "vecs": [_vector_literal(facet.vector) for facet in facets],
        # A zero vector has no direction: its cosine with anything is NaN.
        "has_vecs": [
            facet.vector is not None and float(np.linalg.norm(facet.vector)) > 0 for facet in facets
        ],
        "queries": [facet.query for facet in facets],
        "positive": [facet.kind != "avoid" for facet in facets],
        "now": now,
    }
    if include is None:
        parameters.update(per_facet=per_facet, fresh=fresh)
    else:
        parameters["include"] = list(include)
    # The statement is assembled from two constant fragments; every value is bound.
    rows = await session.execute(text(_EVIDENCE_SQL.format(pool=pool)), parameters)

    z: dict[int, dict[str, float]] = {}
    shares: dict[int, dict[str, float]] = {}
    meta: dict[int, tuple[int, float]] = {}
    for what, article_id, key, value in rows.all():
        if what == "meta":
            meta[article_id] = (int(key), float(value))
        elif value is not None and np.isfinite(float(value)):
            target = z if what == "z" else shares
            target.setdefault(article_id, {})[key] = float(value)
    return [
        Evidence(
            article_id=article_id,
            source_id=source_id,
            age_hours=age_hours,
            z=z.get(article_id, {}),
            rank_share=shares.get(article_id, {}),
        )
        for article_id, (source_id, age_hours) in meta.items()
    ]


def _signal_query(user_id: uuid.UUID, model: str, *, opened: bool, limit: int) -> Any:
    kind = Interaction.kind == KIND_OPEN if opened else Interaction.kind != KIND_OPEN
    return (
        select(
            Interaction.article_id,
            Interaction.kind,
            Interaction.created_at,
            Article.source_id,
            Article.title,
            ArticleEmbedding.embedding,
        )
        .join(Article, Article.id == Interaction.article_id)
        .outerjoin(
            ArticleEmbedding,
            (ArticleEmbedding.article_id == Article.id) & (ArticleEmbedding.model == model),
        )
        .where(Interaction.user_id == user_id, kind)
        .order_by(Interaction.created_at.desc())
        .limit(limit)
    )


async def load_signals(session: AsyncSession, user_id: uuid.UUID, model: str) -> list[Signal]:
    """The newest deliberate signals and, separately, the newest opened links."""
    rows = [
        *(await session.execute(_signal_query(user_id, model, opened=False, limit=SIGNAL_LIMIT))),
        *(await session.execute(_signal_query(user_id, model, opened=True, limit=OPEN_LIMIT))),
    ]
    now = datetime.now(UTC)
    signals = []
    for article_id, kind, created_at, source_id, title, embedding in rows:
        vector = np.asarray(embedding, dtype=np.float32) if embedding is not None else None
        if vector is not None and not float(np.linalg.norm(vector)):
            vector = None
        signals.append(
            Signal(
                article_id=article_id,
                kind=kind,
                age_days=(now - created_at).total_seconds() / 86400,
                source_id=source_id,
                title=title,
                vector=vector,
            )
        )
    return signals


async def rejected_ids(session: AsyncSession, user_id: uuid.UUID) -> frozenset[int]:
    """Every article the reader disliked or hid, with no age limit."""
    rows = await session.execute(
        select(Interaction.article_id).where(
            Interaction.user_id == user_id, Interaction.kind.in_(sorted(REJECTING))
        )
    )
    return frozenset(row[0] for row in rows.all())


async def record(
    session: AsyncSession,
    user_id: uuid.UUID,
    article_id: int,
    kind: str,
    *,
    active: bool,
    context: str,
) -> bool:
    """Set or clear one signal. Returns False when the article does not exist."""
    if await session.scalar(select(Article.id).where(Article.id == article_id)) is None:
        return False
    mine = (Interaction.user_id == user_id) & (Interaction.article_id == article_id)
    if not active:
        await session.execute(delete(Interaction).where(mine, Interaction.kind == kind))
        return True
    opposite = OPPOSITE.get(kind)
    if opposite is not None:
        await session.execute(delete(Interaction).where(mine, Interaction.kind == opposite))
    # Any conflict means the signal is already there, or a concurrent opposite
    # verdict won the race (the partial unique index on like/dislike).
    await session.execute(
        insert(Interaction)
        .values(user_id=user_id, article_id=article_id, kind=kind, context=context)
        .on_conflict_do_nothing()
    )
    return True


async def reactions(
    session: AsyncSession, user_id: uuid.UUID, article_ids: Sequence[int]
) -> dict[int, list[str]]:
    if not article_ids:
        return {}
    rows = await session.execute(
        select(Interaction.article_id, Interaction.kind).where(
            Interaction.user_id == user_id, Interaction.article_id.in_(article_ids)
        )
    )
    found: dict[int, list[str]] = {}
    for article_id, kind in rows.all():
        found.setdefault(article_id, []).append(kind)
    return found


async def seen_ids(
    session: AsyncSession, user_id: uuid.UUID, article_ids: Sequence[int]
) -> set[int]:
    """Those of the articles the reader has met: shown on screen, or marked."""
    if not article_ids:
        return set()
    shown = select(Impression.article_id).where(
        Impression.user_id == user_id, Impression.article_id.in_(article_ids)
    )
    marked = select(Interaction.article_id).where(
        Interaction.user_id == user_id, Interaction.article_id.in_(article_ids)
    )
    return set(await session.scalars(shown.union(marked)))


async def saved_ids(
    session: AsyncSession, user_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[int], int]:
    mine = (Interaction.user_id == user_id) & (Interaction.kind == KIND_SAVE)
    total = await session.scalar(select(func.count()).select_from(Interaction).where(mine))
    rows = await session.execute(
        select(Interaction.article_id)
        .where(mine)
        .order_by(Interaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [row[0] for row in rows.all()], int(total or 0)


async def collab(
    session: AsyncSession, user_id: uuid.UUID, model: str, article_ids: Sequence[int]
) -> dict[int, float]:
    """What readers with a similar taste did with these articles."""
    if not article_ids:
        return {}
    rows = await session.execute(
        _COLLAB_SQL,
        {
            "user_id": user_id,
            "model": model,
            "neighbours": COLLAB_NEIGHBOURS,
            "min_similarity": COLLAB_MIN_SIMILARITY,
            "days": COLLAB_DAYS,
            "ids": list(article_ids),
            "min_readers": COLLAB_MIN_READERS,
        },
    )
    return {article_id: float(weight) for article_id, weight in rows.all()}


async def corpus_mean(session: AsyncSession, model: str, since: datetime) -> np.ndarray | None:
    """The average article vector of the recent period.

    Every taste vector shares this common component ("a text about IT");
    removing it is what makes two readers' vectors comparable.
    """
    # Typed, or the average comes back as the text "[0.01,...]": SQLAlchemy
    # does not know that avg() of a vector is a vector.
    mean = await session.scalar(
        select(func.avg(ArticleEmbedding.embedding, type_=ArticleEmbedding.embedding.type))
        .join(Article, Article.id == ArticleEmbedding.article_id)
        .where(ArticleEmbedding.model == model, Article.published_at >= since)
    )
    return np.asarray(mean, dtype=np.float32) if mean is not None else None


async def save_user_vector(
    session: AsyncSession, user_id: uuid.UUID, model: str, vector: np.ndarray | None
) -> None:
    if vector is None:
        await session.execute(
            delete(UserVector).where(UserVector.user_id == user_id, UserVector.model == model)
        )
        return
    values = {"embedding": vector.tolist(), "updated_at": datetime.now(UTC)}
    await session.execute(
        insert(UserVector)
        .values(user_id=user_id, model=model, **values)
        .on_conflict_do_update(index_elements=["user_id", "model"], set_=values)
    )


async def liked_by_readers_alike(
    session: AsyncSession, user_id: uuid.UUID, model: str, *, limit: int = 200
) -> dict[int, float]:
    """Articles that at least COLLAB_MIN_READERS readers alike liked or saved lately."""
    rows = await session.execute(
        _LIKED_BY_ALIKE_SQL,
        {
            "user_id": user_id,
            "model": model,
            "neighbours": COLLAB_NEIGHBOURS,
            "min_similarity": COLLAB_MIN_SIMILARITY,
            "days": COLLAB_DAYS,
            "min_readers": COLLAB_MIN_READERS,
            "limit": limit,
        },
    )
    return {article_id: float(weight) for article_id, weight in rows.all()}


async def record_impressions(
    session: AsyncSession, user_id: uuid.UUID, article_ids: Sequence[int], context: str
) -> int:
    """Note that the reader saw these articles. Unknown ids are skipped."""
    known = (
        (await session.execute(select(Article.id).where(Article.id.in_(list(set(article_ids))))))
        .scalars()
        .all()
    )
    if not known:
        return 0
    now = datetime.now(UTC)
    statement = insert(Impression).values(
        [
            {
                "user_id": user_id,
                "article_id": article_id,
                "context": context,
                "first_seen_at": now,
                "last_seen_at": now,
            }
            for article_id in known
        ]
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["user_id", "article_id", "context"],
            set_={"times": Impression.times + 1, "last_seen_at": now},
        )
    )
    return len(known)


async def seen_since(
    session: AsyncSession, user_id: uuid.UUID, since: datetime
) -> dict[int, tuple[int, datetime]]:
    """Article id -> (times seen, last seen) for the reader's recent impressions."""
    rows = await session.execute(
        select(Impression.article_id, func.sum(Impression.times), func.max(Impression.last_seen_at))
        .where(Impression.user_id == user_id, Impression.last_seen_at >= since)
        .group_by(Impression.article_id)
        .order_by(func.max(Impression.last_seen_at).desc())
        .limit(SEEN_LIMIT)
    )
    return {article_id: (int(times), last) for article_id, times, last in rows.all()}
