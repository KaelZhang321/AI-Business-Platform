CREATE TABLE IF NOT EXISTS rag_metrics
(
    query String,
    vector_hit UInt16,
    keyword_hit UInt16,
    graph_hit UInt16,
    final_count UInt16,
    top_ids Array(String),
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (created_at, query)
TTL created_at + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;
