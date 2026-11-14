"""Persist raw deliveries and expose validated observations to Step 3."""

import json
from contextlib import closing
from datetime import datetime, timezone

from .storage import connect_database
from .validation import json_string, utc_string, validate_observation



def _raw_payload(raw):
    try:
        return json_string(raw), "json"
    except (TypeError, ValueError, OverflowError):
        # Invalid Python objects are not JSON telemetry. Retain a diagnostic
        # representation for review rather than discarding the delivery.
        return repr(raw), "python_repr"


def ingest_batch(measurements, db_path="data/telemetry.sqlite", reference_time=None):
    """Validate and persist a batch atomically; return only new clean records.

    Identity is (astronaut_id, metric, captured_at in UTC, source). Retransmissions
    with the same normalized value, unit and context are duplicates. Changed
    values or context at that identity are conflicts; the first record stays.
    Every delivery, including duplicates and conflicts, has a raw audit row.
    A transaction failure rolls back the entire batch and propagates the error.
    """
    if isinstance(measurements, (str, bytes, dict)):
        raise TypeError("measurements must be an iterable of observation objects")
    now = reference_time if reference_time is not None else datetime.now(timezone.utc)
    received_at = utc_string(now)
    with closing(connect_database(db_path)) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            return _ingest_on_connection(connection, measurements, received_at=received_at, reference_time=now)


def _ingest_on_connection(connection, measurements, *, received_at, reference_time, sensor_packet_id=None):
    """Write with the caller's transaction, including its packet status change."""
    summary = {"accepted": [], "quarantined": [], "duplicates": [], "conflicts": []}
    for raw in measurements:
        result = validate_observation(raw, reference_time=reference_time)
        status, errors = result["status"], result["errors"]
        observation = result["observation"]
        if observation is not None:
            identity = tuple(observation[key] for key in (
                "astronaut_id", "metric", "captured_at", "source"
            ))
            content = (
                observation["unit"], json_string(observation["value"]),
                json_string(observation["context"]),
            )
            existing = connection.execute(
                """SELECT unit, value_json, context_json
                   FROM validated_observations
                   WHERE astronaut_id=? AND metric=? AND captured_at=? AND source=?""",
                identity,
            ).fetchone()
            if existing is not None:
                status = "duplicate" if existing == content else "conflict"
                if status == "conflict":
                    errors = ["A different measurement already exists at this identity"]

        payload, encoding = _raw_payload(raw)
        cursor = connection.execute(
            """INSERT INTO raw_measurements
               (received_at, payload, payload_encoding, status, errors_json, sensor_packet_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (received_at, payload, encoding, status, json_string(errors), sensor_packet_id),
        )
        raw_id = cursor.lastrowid
        if status == "accepted":
            connection.execute(
                """INSERT INTO validated_observations
                   (raw_id, astronaut_id, metric, captured_at, source,
                    unit, value_json, context_json, quality_flags_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (raw_id, *identity, *content, json_string(observation["quality_flags"])),
            )
            summary["accepted"].append(observation)
        else:
            bucket = {"quarantined": "quarantined", "duplicate": "duplicates", "conflict": "conflicts"}[status]
            summary[bucket].append({
                "raw_id": raw_id, "errors": errors, "observation": observation,
            })
    return summary


def get_validated_observations(db_path, astronaut_id, limit=100):
    """Return a crew member's clean history, newest first, for Step 3.

    quality_flags describe transformations, not medical risk or verified sensor
    reliability. Historical records remain available for downstream baselines.
    """
    if not isinstance(astronaut_id, str) or not astronaut_id.strip():
        raise ValueError("astronaut_id is required")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10000:
        raise ValueError("limit must be an integer between 1 and 10000")
    with closing(connect_database(db_path)) as connection:
        rows = connection.execute(
            """SELECT astronaut_id, metric, captured_at, source, unit,
                      value_json, context_json, quality_flags_json
               FROM validated_observations WHERE astronaut_id=?
               ORDER BY captured_at DESC, id DESC LIMIT ?""",
            (astronaut_id, limit),
        ).fetchall()
    return [
        {"astronaut_id": row[0], "metric": row[1], "captured_at": row[2],
         "source": row[3], "unit": row[4], "value": json.loads(row[5]),
         "context": json.loads(row[6]), "quality_flags": json.loads(row[7])}
        for row in rows
    ]
