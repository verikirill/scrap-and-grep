-- One row per thing that happened: an article served in a feed, seen on
-- screen, opened, marked; a digest built or opened; a suggestion decided; a
-- call through MCP. Only ids and numbers, never texts or addresses.
--
-- Empty values are zeros rather than NULLs: 0 for an article or a position,
-- the nil UUID for a profile or a list, '' for a string.
CREATE TABLE IF NOT EXISTS events
(
    ts            DateTime64(3, 'UTC'),
    event_id      UUID,
    user_id       UUID,
    is_guest      Bool,
    event         LowCardinality(String),
    -- Where it happened: feed, digest, profiles, share, mcp.
    surface       LowCardinality(String),
    article_id    UInt64,
    source_id     UInt32,
    category      LowCardinality(String),
    -- The list the article was in: a feed snapshot or a digest.
    request_id    UUID,
    -- 1-based place in that list; 0 when unknown.
    position      UInt16,
    -- Why the article was in the list: ranked, explore, newest, digest.
    slot          LowCardinality(String),
    profile_id    UUID,
    -- The reader had at least one profile that adapts to their marks.
    adaptive      Bool,
    score         Float32,
    -- The parts of the score at the moment it was served: what a learned
    -- ranker is trained on, so training sees what serving saw.
    features      Map(LowCardinality(String), Float32),
    -- Which ranker served the list (hand, learned) and its version.
    variant       LowCardinality(String),
    model_version LowCardinality(String),
    -- A short machine label: the MCP tool, a digest's origin.
    detail        LowCardinality(String),
    value         Float32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (event, user_id, ts)
-- Guests are throwaway accounts that live a day; their events go soon after.
TTL toDateTime(ts) + INTERVAL 180 DAY DELETE,
    toDateTime(ts) + INTERVAL 2 DAY DELETE WHERE is_guest
-- Lets the writer retry a batch with the same token without doubling it.
SETTINGS non_replicated_deduplication_window = 1000;
