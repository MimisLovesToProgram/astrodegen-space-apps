"""Version the data contract shared by sensors, validation, and assessment."""

from datetime import datetime, timezone

from .adapters import SENSOR_FIELDS
from .validation import BOOLEAN_METRICS, NUMERIC_RULES, REQUIRED_FIELDS, utc_string


CONTRACT_VERSION = "astrocrates.observation.v1"


def observation_contract():
    # Derive the published units and bounds from the actual validator, so the
    # handoff specification cannot silently drift from supported measurements.
    metrics = {
        metric: {"unit": rule[0], "minimum": rule[1], "maximum": rule[2],
                 "value_type": "integer" if rule[3] else "number"}
        for metric, rule in NUMERIC_RULES.items()
    }
    metrics.update({metric: {"unit": "bool", "value_type": "boolean"} for metric in sorted(BOOLEAN_METRICS)})
    metrics["symptoms"] = {"unit": "list", "value_type": "list_of_nonempty_strings"}
    return {
        "contract_version": CONTRACT_VERSION,
        "required_input_fields": sorted(REQUIRED_FIELDS),
        "additional_output_fields": ["context", "quality_flags"],
        "timestamp": {"format": "aware ISO-8601, normalized to UTC", "maximum_future_seconds": 300},
        "history": {"order": "newest_first", "default_limit": 250, "maximum_limit": 10000,
                    "limit_unit": "individual observations, not days"},
        "metrics": metrics,
        "sensor_mapping": {field: {"metric": value[0], "unit": value[1]} for field, value in SENSOR_FIELDS.items()},
        "prototype_assumptions": {"hr": "resting heart rate", "hrv": "RMSSD in milliseconds"},
        "bounds_purpose": "prototype data-quality safeguards; health interpretation belongs to Step 3",
    }


def history_handoff(astronaut_id, observations, limit):
    # Keep the old history command's list format compatible; this separate
    # envelope provides a version and truncation context for a Step 3 consumer.
    return {"contract_version": CONTRACT_VERSION, "astronaut_id": astronaut_id,
            "generated_at": utc_string(datetime.now(timezone.utc)),
            "order": "newest_first", "observation_limit": limit,
            "may_be_truncated": len(observations) >= limit, "observations": observations}
