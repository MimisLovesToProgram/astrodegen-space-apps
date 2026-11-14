"""Telemetry data-quality checks, independent of health-risk assessment.

Bounds are illustrative prototype safeguards, not clinical or NASA limits.
A source label records provenance; it does not authenticate a sensor.
"""

import json
import math
from datetime import datetime, timedelta, timezone


NUMERIC_RULES = {
    "hr_resting": ("bpm", 20, 250, False),
    "hrv_rmssd": ("ms", 0, 500, False),
    "spo2": ("%", 0, 100, False),
    "temp_c": ("C", 20, 46, False),
    "radiation_msv_cumulative": ("mSv", 0, None, False),
    "sleep_h": ("h", 0, 24, False),
    "sleep_quality": ("score_1_5", 1, 5, True),
    "mood": ("score_1_5", 1, 5, True),
    "activity_pct_target": ("%", 0, 500, False),
    "mission_day": ("day", 0, None, True),
}
BOOLEAN_METRICS = {"exercise_logged", "social_interaction"}
REQUIRED_FIELDS = {"astronaut_id", "metric", "value", "unit", "captured_at", "source"}


def utc_string(value):
    """Serialize an aware datetime in a consistently sortable UTC format."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A timezone-aware datetime is required")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def json_string(value):
    """Encode JSON without silently accepting NaN, infinity or custom objects."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate_observation(raw, reference_time=None):
    """Return accepted normalized data, or quarantined data with error reasons.

    Aware ISO-8601 timestamps are required. Historical measurements are allowed;
    timestamps more than five minutes ahead of reference_time are quarantined.
    """
    now = reference_time if reference_time is not None else datetime.now(timezone.utc)
    utc_string(now)

    def reject(reason):
        return {"status": "quarantined", "errors": [reason], "observation": None}

    if not isinstance(raw, dict):
        return reject("Measurement must be an object")
    missing = REQUIRED_FIELDS - raw.keys()
    if missing:
        return reject("Missing fields: " + ", ".join(sorted(missing)))
    for field in ("astronaut_id", "metric", "unit", "source", "captured_at"):
        if not isinstance(raw[field], str) or not raw[field].strip():
            return reject(f"{field} must be a nonempty string")
    try:
        json_string(raw)
    except (TypeError, ValueError, OverflowError):
        return reject("Measurement must contain finite, JSON-serializable values")
    context = raw.get("context", {})
    if not isinstance(context, dict):
        return reject("context must be an object")
    try:
        captured = datetime.fromisoformat(raw["captured_at"].replace("Z", "+00:00"))
        timestamp = utc_string(captured)
        if captured > now + timedelta(minutes=5):
            return reject("captured_at is more than five minutes in the future")
    except (ValueError, OverflowError):
        return reject("captured_at must be an ISO-8601 timestamp with a timezone")

    metric, unit, value = raw["metric"], raw["unit"], raw["value"]
    flags = []
    if metric == "symptoms":
        if unit != "list" or not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            return reject("symptoms requires a list of nonempty strings and unit 'list'")
    elif metric in BOOLEAN_METRICS:
        if unit != "bool" or not isinstance(value, bool):
            return reject(f"{metric} requires a boolean value and unit 'bool'")
    elif metric in NUMERIC_RULES:
        canonical_unit, lower, upper, integer = NUMERIC_RULES[metric]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return reject("value must be a finite number, not a boolean")
        try:
            if not math.isfinite(value):
                return reject("value must be finite")
            if metric == "temp_c" and unit == "F":
                value = (value - 32) * 5 / 9
                flags.append("unit_converted:F_to_C")
                unit = "C"
            elif metric == "sleep_h" and unit == "min":
                value = value / 60
                flags.append("unit_converted:min_to_h")
                unit = "h"
        except OverflowError:
            return reject("value exceeds the supported numeric range")
        if unit != canonical_unit:
            return reject(f"{metric} requires unit {canonical_unit!r}")
        if value < lower or (upper is not None and value > upper):
            return reject(f"value outside prototype data-quality bounds for {metric}")
        if integer:
            if value != int(value):
                return reject(f"{metric} requires an integer")
            value = int(value)
        else:
            value = float(value)
    else:
        return reject(f"Unsupported metric: {metric}")

    # Round-trip JSON detaches nested context from the caller's mutable input.
    observation = json.loads(json_string({
        "astronaut_id": raw["astronaut_id"], "metric": metric,
        "value": value, "unit": unit, "captured_at": timestamp,
        "source": raw["source"], "context": context, "quality_flags": flags,
    }))
    return {"status": "accepted", "errors": [], "observation": observation}
