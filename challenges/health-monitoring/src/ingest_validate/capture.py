"""Step 1: persist timestamped packets before any measurement validation."""

from contextlib import closing
from datetime import datetime, timezone

from .service import _raw_payload
from .storage import connect_database
from .validation import utc_string


def capture_sensor_packets(packets, db_path="data/telemetry.sqlite", *,
                           assume_utc=False, reference_time=None):
    """Commit a finite batch and return its durable packet IDs.

    Sensor content is not validated here. Each delivery gets one inbox row,
    including invalid data and retransmissions. Capture and receive timestamps
    are separate; received_at is always the actual UTC clock. validation_time
    freezes the receive clock (or explicit simulation clock) for later checks.
    Non-JSON input keeps a diagnostic representation that will be quarantined.
    """
    if isinstance(packets, (str, bytes, dict)):
        raise TypeError("packets must be an iterable of sensor packet objects")
    if not isinstance(assume_utc, bool):
        raise TypeError("assume_utc must be a boolean")
    if reference_time is not None:
        utc_string(reference_time)
    packet_ids = []
    with closing(connect_database(db_path)) as connection:
        with connection:
            for packet in packets:
                received = datetime.now(timezone.utc)
                payload, encoding = _raw_payload(packet)
                captured = packet.get("timestamp") if isinstance(packet, dict) else None
                cursor = connection.execute(
                    """INSERT INTO sensor_packets
                       (received_at, captured_at, source, payload, payload_encoding,
                        assume_utc, validation_time) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (utc_string(received), captured if isinstance(captured, str) else None,
                     "synthetic_biosensors", payload, encoding, int(assume_utc),
                     utc_string(reference_time if reference_time is not None else received)),
                )
                packet_ids.append(cursor.lastrowid)
    return packet_ids
