CREATE DATABASE IF NOT EXISTS  sat;

CREATE TABLE IF NOT EXISTS sat.coordinates (
    task_id        UInt64,
    chunk_index    UInt32,
    timestamp      DateTime64(3),
    latitude       Float64,
    longitude      Float64,
    altitude       Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (task_id, timestamp)
SETTINGS index_granularity = 8192;