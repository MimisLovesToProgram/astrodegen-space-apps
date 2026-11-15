"""Process bounded batches from the durable sensor inbox."""

import json
from contextlib import closing
from datetime import datetime, timezone

from .adapters import sensor_observations
from .service import _ingest_on_connection
from .storage import connect_database
from .validation import json_string, utc_string


def validate_pending_packets(db_path="data/telemetry.sqlite", *, limit=100, packet_ids=None):
    """Commit results and processed markers together; failures leave work pending."""
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("limit must be an integer between 1 and 500")
    summary = {"accepted": [], "quarantined": [], "duplicates": [], "conflicts": []}
    params = []
    condition = "status='pending'"
    if packet_ids is not None:
        packet_ids = list(packet_ids)
        if len(packet_ids) > 500 or any(type(item) is not int or item < 1 for item in packet_ids):
            raise ValueError("packet_ids must contain at most 500 positive integers")
        if not packet_ids:
            return {"packet_ids": [], "ingestion": summary}
        condition += " AND id IN (" + ",".join("?" for _ in packet_ids) + ")"
        params.extend(packet_ids)
    processed = []
    with closing(connect_database(db_path)) as connection:
        with connection:
            # Selecting pending rows and marking them complete share this
            # transaction. A failure rolls back both results and markers.
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                f"""SELECT id, payload, payload_encoding, assume_utc, received_at, validation_time
                    FROM sensor_packets WHERE {condition} ORDER BY id LIMIT ?""",
                (*params, limit),
            ).fetchall()
            for packet_id, payload, encoding, assume_utc, received, validation_time in rows:
                packet = json.loads(payload) if encoding == "json" else payload
                # Diagnostic Python representations are never evaluated; they
                # remain strings that the validator will quarantine.
                result = _ingest_on_connection(
                    connection, sensor_observations([packet], assume_utc=bool(assume_utc)),
                    received_at=received,
                    reference_time=datetime.fromisoformat(validation_time.replace("Z", "+00:00")),
                    sensor_packet_id=packet_id,
                )
                connection.execute(
                    """UPDATE sensor_packets SET status='processed', processed_at=?, counts_json=? WHERE id=?""",
                    (utc_string(datetime.now(timezone.utc)),
                     json_string({key: len(records) for key, records in result.items()}), packet_id),
                )
                processed.append(packet_id)
                for key in summary:
                    summary[key].extend(result[key])
    return {"packet_ids": processed, "ingestion": summary}
