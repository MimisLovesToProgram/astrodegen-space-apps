"""Shared SQLite schema, including a durable inbox for Step 1 packets."""

import sqlite3
from pathlib import Path


SCHEMA_VERSION = 2
# The inbox owns original deliveries, raw_measurements records metric outcomes,
# and validated_observations contains only unique, accepted normalized data.
SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_packets (
    id INTEGER PRIMARY KEY,
    received_at TEXT NOT NULL,
    captured_at TEXT,
    source TEXT NOT NULL,
    payload TEXT NOT NULL,
    payload_encoding TEXT NOT NULL,
    assume_utc INTEGER NOT NULL CHECK (assume_utc IN (0, 1)),
    validation_time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processed')),
    processed_at TEXT,
    counts_json TEXT
);
CREATE INDEX IF NOT EXISTS pending_sensor_packets
ON sensor_packets (id) WHERE status = 'pending';
CREATE TABLE IF NOT EXISTS raw_measurements (
    id INTEGER PRIMARY KEY,
    received_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    payload_encoding TEXT NOT NULL,
    status TEXT NOT NULL,
    errors_json TEXT NOT NULL,
    sensor_packet_id INTEGER REFERENCES sensor_packets(id)
);
CREATE INDEX IF NOT EXISTS raw_packet_measurements ON raw_measurements (sensor_packet_id);
CREATE TABLE IF NOT EXISTS validated_observations (
    id INTEGER PRIMARY KEY,
    raw_id INTEGER NOT NULL REFERENCES raw_measurements(id),
    astronaut_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    source TEXT NOT NULL,
    unit TEXT NOT NULL,
    value_json TEXT NOT NULL,
    context_json TEXT NOT NULL,
    quality_flags_json TEXT NOT NULL,
    UNIQUE (astronaut_id, metric, captured_at, source)
);
CREATE INDEX IF NOT EXISTS observations_history
ON validated_observations (astronaut_id, captured_at DESC, id DESC);
CREATE TABLE IF NOT EXISTS quality_checks (
    scope_key TEXT PRIMARY KEY,
    policy_key TEXT NOT NULL,
    policy_name TEXT NOT NULL,
    astronaut_id TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    policy_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quality_alerts (
    alert_key TEXT PRIMARY KEY,
    scope_key TEXT NOT NULL,
    policy_name TEXT NOT NULL,
    astronaut_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    source TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('missing','stale','future','sampling_gap')),
    status TEXT NOT NULL CHECK (status IN ('active','resolved')),
    first_detected_at TEXT NOT NULL,
    last_checked_at TEXT NOT NULL,
    resolved_at TEXT,
    occurrences INTEGER NOT NULL,
    evidence_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS quality_alert_scope ON quality_alerts(scope_key,status);
CREATE INDEX IF NOT EXISTS quality_alert_history ON quality_alerts(astronaut_id,last_checked_at DESC);
"""


def connect_database(db_path):
    """Open persistent storage, preserving databases created before the inbox.

    WAL allows readers during a writer transaction. Schema migration runs only
    for an older user_version and is serialized with other writers.
    """
    if str(db_path) == ":memory:":
        raise ValueError("Use a file path so capture and validation share persistent data")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), timeout=30)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise ValueError("Database schema is newer than this application")
        if version < SCHEMA_VERSION:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
                    # Older databases already have raw_measurements; add the
                    # nullable link before creating its index. Keep old rows.
                    exists = connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='raw_measurements'"
                    ).fetchone()
                    if exists:
                        columns = {row[1] for row in connection.execute("PRAGMA table_info(raw_measurements)")}
                        if "sensor_packet_id" not in columns:
                            connection.execute(
                                "ALTER TABLE raw_measurements ADD COLUMN sensor_packet_id INTEGER REFERENCES sensor_packets(id)"
                            )
                    for statement in SCHEMA.split(";"):
                        if statement.strip():
                            connection.execute(statement)
                    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    except Exception:
        connection.close()
        raise
    return connection
