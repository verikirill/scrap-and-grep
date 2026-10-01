-- Daily counts for the analytics page, kept up to date as events arrive.
--
-- `kind` is the event, plus "seen" for every article the reader saw or acted
-- on: a card opened or liked within a second of appearing never reports an
-- impression, yet it was seen. Rates are over distinct (reader, article)
-- pairs, so an article opened twice counts once. Counts stay when an account
-- is deleted: they hold no ids, only hashed sketches of them.
CREATE TABLE IF NOT EXISTS events_daily
(
    day       Date,
    kind      LowCardinality(String),
    surface   LowCardinality(String),
    slot      LowCardinality(String),
    variant   LowCardinality(String),
    adaptive  Bool,
    is_guest  Bool,
    category  LowCardinality(String),
    source_id UInt32,
    events    SimpleAggregateFunction(sum, UInt64),
    readers   AggregateFunction(uniq, UUID),
    pairs     AggregateFunction(uniq, UUID, UInt64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, kind, surface, slot, variant, adaptive, is_guest, category, source_id)
TTL day + INTERVAL 400 DAY;

CREATE MATERIALIZED VIEW IF NOT EXISTS events_daily_mv TO events_daily AS
SELECT
    toDate(ts) AS day,
    arrayJoin(
        if(event IN ('impression', 'open', 'like', 'dislike', 'save', 'hide'), [event, 'seen'], [event])
    ) AS kind,
    surface,
    slot,
    variant,
    adaptive,
    is_guest,
    category,
    source_id,
    count() AS events,
    uniqState(user_id) AS readers,
    uniqState(user_id, article_id) AS pairs
FROM events
GROUP BY day, kind, surface, slot, variant, adaptive, is_guest, category, source_id;
