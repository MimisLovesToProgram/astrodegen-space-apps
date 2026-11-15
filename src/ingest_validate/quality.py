"""Data freshness and acceptance summaries, independent of health assessment."""

import math
from datetime import datetime, timezone

from .adapters import SENSOR_FIELDS
from .validation import utc_string


def summarize_audit(audit):
    """Expose observed acceptance rates, not claimed physical-sensor accuracy."""
    sources = {}
    for row in audit["results"]:
        counts = sources.setdefault(row["source"], {
            "accepted": 0, "quarantined": 0, "duplicate": 0, "conflict": 0,
        })
        counts[row["status"]] = row["total"]
    for counts in sources.values():
        # Retransmissions do not improve or reduce the quality rate.
        denominator = counts["accepted"] + counts["quarantined"] + counts["conflict"]
        counts["data_acceptance_rate"] = counts["accepted"] / denominator if denominator else None
    return {"scope": "all_database", "packets": audit["packets"], "sources": sources}


def quality_report(history, astronaut_id, *, max_age_seconds, reference_time=None,
                   expected_metrics=None, history_limit=10000, source=None,
                   expected_interval_seconds=None, gap_tolerance_fraction=0.1):
    """Describe missing/stale metrics without rejecting physiological changes.

    Missing means absent from the queried history window. Stale means the
    newest accepted reading is older than the explicit age policy. No default
    sampling frequency is invented for daily versus continuous measurements.
    """
    if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, (int, float)) or not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be a positive finite number")
    clock = reference_time if reference_time is not None else datetime.now(timezone.utc)
    generated = utc_string(clock)
    if source is not None and (not isinstance(source, str) or not source.strip()):
        raise ValueError("source must be a nonempty string")
    metrics = sorted(set(expected_metrics if expected_metrics is not None else (
        value[0] for value in SENSOR_FIELDS.values()
    )))
    if not metrics or any(not isinstance(metric, str) or not metric for metric in metrics):
        raise ValueError("expected_metrics must contain nonempty metric names")
    latest = {}
    for observation in history:
        # Keep the latest timestamp even if a caller supplies unsorted history.
        if observation["astronaut_id"] != astronaut_id or (source is not None and observation.get("source") != source):
            continue
        timestamp = datetime.fromisoformat(observation["captured_at"].replace("Z", "+00:00"))
        metric = observation["metric"]
        if metric not in latest or timestamp > latest[metric]:
            latest[metric] = timestamp
    rows = []
    for metric in metrics:
        captured = latest.get(metric)
        age = (clock - captured).total_seconds() if captured is not None else None
        # Explicitly surface clock mismatches in synthetic replays.
        status = "missing" if captured is None else (
            "future" if age < 0 else "stale" if age > max_age_seconds else "fresh"
        )
        rows.append({"metric": metric, "status": status,
                     "latest_captured_at": utc_string(captured) if captured is not None else None,
                     "age_seconds": age})
    fresh = sum(row["status"] == "fresh" for row in rows)
    report = {
        "astronaut_id": astronaut_id, "reference_time": generated,
        "source": source,
        "max_age_seconds": max_age_seconds, "history_observations": len(history),
        "history_limit": history_limit, "history_may_be_truncated": len(history) >= history_limit,
        "fresh_metric_fraction": fresh / len(rows), "metrics": rows,
        "missing_metrics": [row["metric"] for row in rows if row["status"] == "missing"],
        "stale_metrics": [row["metric"] for row in rows if row["status"] == "stale"],
        "future_metrics": [row["metric"] for row in rows if row["status"] == "future"],
    }
    if expected_interval_seconds is not None:
        report["sampling"] = sampling_gaps(
            history, astronaut_id, expected_interval_seconds=expected_interval_seconds,
            reference_time=clock, expected_metrics=metrics, source=source,
            tolerance_fraction=gap_tolerance_fraction,
        )
    return report


def sampling_gaps(history, astronaut_id, *, expected_interval_seconds, reference_time,
                  expected_metrics, source=None, tolerance_fraction=0.1):
    """Report observed timing gaps separately for each metric and source."""
    if isinstance(expected_interval_seconds, bool) or not isinstance(expected_interval_seconds, (int, float)) or not math.isfinite(expected_interval_seconds) or expected_interval_seconds <= 0:
        raise ValueError("expected_interval_seconds must be a positive finite number")
    if isinstance(tolerance_fraction, bool) or not isinstance(tolerance_fraction, (int, float)) or not math.isfinite(tolerance_fraction) or not 0 <= tolerance_fraction < 1:
        raise ValueError("tolerance_fraction must be finite and between zero and one, excluding one")
    utc_string(reference_time)
    streams = {}
    for observation in history:
        if observation["astronaut_id"] != astronaut_id or observation["metric"] not in expected_metrics:
            continue
        sensor = observation.get("source", "unspecified")
        if source is not None and sensor != source:
            continue
        captured = datetime.fromisoformat(observation["captured_at"].replace("Z", "+00:00"))
        # We exclude future readings from cadence calculations and deduplicate
        # equal timestamps, so neither clock errors nor retransmissions hide gaps.
        if captured <= reference_time:
            streams.setdefault((observation["metric"], sensor), set()).add(captured)
    threshold = expected_interval_seconds * (1 + tolerance_fraction)
    historical = []
    overdue = []
    for (metric, sensor), timestamps in sorted(streams.items()):
        ordered = sorted(timestamps)
        # We never combine different sources into one stream: a healthy device
        # must not fill the timing gaps left by another device.
        for start, end in zip(ordered, ordered[1:]):
            duration = (end - start).total_seconds()
            if duration > threshold:
                historical.append({"metric": metric, "source": sensor,
                                   "start": utc_string(start), "end": utc_string(end),
                                   "duration_seconds": duration})
        age = (reference_time - ordered[-1]).total_seconds()
        if age > threshold:
            overdue.append({"metric": metric, "source": sensor,
                            "latest_captured_at": utc_string(ordered[-1]), "age_seconds": age,
                            "overdue_seconds": age - expected_interval_seconds})
    return {"expected_interval_seconds": expected_interval_seconds,
            "tolerance_fraction": tolerance_fraction,
            "gap_threshold_seconds": threshold, "stream_count": len(streams),
            "historical_gaps": historical, "overdue_streams": overdue}
