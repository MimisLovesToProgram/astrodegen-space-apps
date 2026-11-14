"""Translate this repository's synthetic biosensors packets into observations."""

from datetime import datetime, timezone

from .service import ingest_batch


# Sensor field -> Step 2 metric and canonical unit.
SENSOR_FIELDS = {
    "hr": ("hr_resting", "bpm"),
    "hrv": ("hrv_rmssd", "ms"),
    "spo2": ("spo2", "%"),
    "temp_c": ("temp_c", "C"),
    "radiation_msv_cumulative": ("radiation_msv_cumulative", "mSv"),
    "sleep_h": ("sleep_h", "h"),
    "sleep_quality": ("sleep_quality", "score_1_5"),
    "mood": ("mood", "score_1_5"),
    "symptoms": ("symptoms", "list"),
    "exercise_logged": ("exercise_logged", "bool"),
    "social_interaction": ("social_interaction", "bool"),
    "mission_day": ("mission_day", "day"),
}


def sensor_observations(packets, *, assume_utc=False):
    """Expand full biosensors packets; missing fields are quarantined downstream.

    This adapter is for the synthetic biosensors.py schema, not real sensors.
    Original packets are retained on each raw observation for inspection.
    Naive timestamps stay invalid unless the caller explicitly assumes UTC.
    """
    if isinstance(packets, (str, bytes, dict)):
        raise TypeError("packets must be an iterable of sensor packet objects")
    for packet in packets:
        if not isinstance(packet, dict):
            yield packet
            continue
        timestamp = packet.get("timestamp")
        context = {"simulated": True}
        if assume_utc and isinstance(timestamp, str):
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    timestamp = parsed.replace(tzinfo=timezone.utc).isoformat()
                    context["timestamp_timezone_assumed"] = "UTC"
            except ValueError:
                pass  # Let the validator audit the malformed timestamp.
        for field, (metric, unit) in SENSOR_FIELDS.items():
            yield {
                "astronaut_id": packet.get("crew_id"), "metric": metric,
                "value": packet.get(field), "unit": unit,
                "captured_at": timestamp, "source": "synthetic_biosensors",
                "context": context, "sensor_packet": packet,
            }


def ingest_sensor_packets(packets, db_path="data/telemetry.sqlite", *, assume_utc=False, reference_time=None):
    """Run Step 1 packets through the same atomic Step 2 storage path."""
    return ingest_batch(
        sensor_observations(packets, assume_utc=assume_utc),
        db_path=db_path, reference_time=reference_time,
    )
