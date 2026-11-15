"""Connect the simulator, validation/storage, and a future assessment function."""

from .adapters import ingest_sensor_packets
from .service import get_validated_observations


def process_sensor_packets(packets, db_path="data/telemetry.sqlite", *,
                           assume_utc=False, reference_time=None,
                           assess=None, history_limit=250):
    """Ingest packets and send clean history to assess(astronaut_id, history).

    The optional assessment function belongs to Step 3; no risk scoring is
    implemented here. It runs once for each crew member with new accepted data.
    Duplicates and quarantined data alone do not trigger assessment. Ingestion
    commits before assessment: if assessment fails, clean history is retained
    and can be read and reassessed with get_validated_observations.
    """
    if isinstance(history_limit, bool) or not isinstance(history_limit, int) or not 1 <= history_limit <= 10000:
        raise ValueError("history_limit must be an integer between 1 and 10000")
    if assess is not None and not callable(assess):
        raise TypeError("assess must be callable")
    ingestion = ingest_sensor_packets(
        packets, db_path, assume_utc=assume_utc, reference_time=reference_time,
    )
    crew_ids = sorted({item["astronaut_id"] for item in ingestion["accepted"]})
    # Only crews with new accepted data need reassessment. Their clean history
    # includes previous readings, not just the latest packet's measurements.
    histories = {
        crew_id: get_validated_observations(db_path, crew_id, history_limit)
        for crew_id in crew_ids
    }
    assessments = {
        # Assessment happens after ingestion commits, so a failed risk engine
        # cannot erase already accepted data. Durable assessment retries are
        # the responsibility of the future Step 3 job layer.
        crew_id: assess(crew_id, history) for crew_id, history in histories.items()
    } if assess is not None else {}
    return {
        "ingestion": ingestion, "step3_history": histories,
        "assessment_status": "completed" if assess is not None else "not_configured",
        "assessments": assessments,
    }


def simulated_mission():
    """Return all 21 existing story packets without the simulator's sleep loop.

    The fixed mission clock lets the future-dated synthetic story run today.
    This does not change timestamp checks on other ingestion paths.
    """
    from biosensors import Crew, reading_from
    from datetime import datetime, timezone

    packets = [reading_from(crew_id, arc[day - 1], day)
               for day in range(1, 8) for crew_id, arc in Crew.items()]
    reference_time = max(datetime.fromisoformat(packet["timestamp"]) for packet in packets)
    return packets, reference_time.replace(tzinfo=timezone.utc)
