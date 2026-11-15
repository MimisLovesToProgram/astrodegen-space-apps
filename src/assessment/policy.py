"""Load explicit assessment rules; do not hide thresholds inside engine code."""

import hashlib
import json
import math
from pathlib import Path

from ingest_validate.validation import BOOLEAN_METRICS, NUMERIC_RULES, json_string


DOMAINS = ("cardiovascular", "immune", "behavioral", "bone_loss")
COLORS = ("green", "yellow", "orange", "red")
FEATURES = {"value", "count", "baseline_change", "baseline_change_pct", "mad_deviation", "trend_per_day", "contains_any", "hours_since_true", "missed_mission_days"}
OPERATORS = {"gt", "gte", "lt", "lte", "eq"}


def _finite(value):
    try:
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        return False


def validate_policy(policy):
    """Validate rule structure and return a detached, JSON-safe policy."""
    if not isinstance(policy, dict) or policy.get("schema_version") != "astrocrates.assessment-policy.v1":
        raise ValueError("Unsupported assessment policy schema")
    allowed = {"schema_version", "policy_id", "description", "purpose", "simulation_only", "source",
               "metric_sources", "max_age_seconds", "domains"}
    if set(policy) - allowed:
        raise ValueError("Unknown policy fields: " + ", ".join(sorted(set(policy) - allowed)))
    if not isinstance(policy.get("policy_id"), str) or not policy["policy_id"].strip() or len(policy["policy_id"]) > 100:
        raise ValueError("policy_id is required")
    if policy.get("purpose") not in {"synthetic_demo", "team_defined"} or type(policy.get("simulation_only")) is not bool:
        raise ValueError("Declare purpose and simulation_only explicitly")
    if policy["purpose"] == "synthetic_demo" and not policy["simulation_only"]:
        raise ValueError("Synthetic demo policies must be restricted to simulated observations")
    if not isinstance(policy.get("source"), str) or not policy["source"].strip():
        raise ValueError("A default sensor source is required")
    age = policy.get("max_age_seconds")
    if not _finite(age) or age <= 0:
        raise ValueError("max_age_seconds must be positive and finite")
    known_metrics = set(NUMERIC_RULES) | BOOLEAN_METRICS | {"symptoms"}
    sources = policy.get("metric_sources", {})
    if not isinstance(sources, dict) or any(key not in known_metrics or not isinstance(value, str) or not value.strip()
                                            for key, value in sources.items()):
        raise ValueError("metric_sources must map supported metrics to source names")
    domains = policy.get("domains")
    if not isinstance(domains, dict) or set(domains) != set(DOMAINS):
        raise ValueError("Define cardiovascular, immune, behavioral, and bone_loss domains")
    for name, domain in domains.items():
        _validate_domain(name, domain, known_metrics)
    # We fingerprint the complete policy, including its purpose, so changing
    # rules cannot silently reuse results calculated by a previous revision.
    return json.loads(json_string(policy))


def policy_digest(policy):
    return hashlib.sha256(json_string(validate_policy(policy)).encode()).hexdigest()


def load_policy(path):
    return validate_policy(json.loads(Path(path).read_text()))


def _validate_domain(name, domain, known_metrics):
    if not isinstance(domain, dict) or set(domain) != {"rules", "bands"}:
        raise ValueError(f"{name} must define rules and bands")
    rules, bands = domain["rules"], domain["bands"]
    if not isinstance(rules, list) or not 1 <= len(rules) <= 100:
        raise ValueError(f"{name} requires 1 to 100 rules")
    ids = set()
    for rule in rules:
        _validate_rule(rule, known_metrics)
        if rule["id"] in ids:
            raise ValueError(f"Duplicate rule ID in {name}")
        ids.add(rule["id"])
    if not isinstance(bands, list) or len(bands) != 4:
        raise ValueError(f"{name} requires four score bands")
    previous = -1
    for level, band in enumerate(bands):
        if not isinstance(band, dict) or set(band) != {"level", "min_points"}:
            raise ValueError("Each band requires level and min_points")
        threshold = band["min_points"]
        if type(band["level"]) is not int or band["level"] != level or not _finite(threshold) or not previous < threshold <= 100:
            raise ValueError("Bands must have increasing thresholds and levels 0, 1, 2, 3")
        if level == 0 and threshold != 0:
            raise ValueError("The green band must start at zero points")
        previous = threshold


def _validate_rule(rule, known_metrics):
    required = {"id", "metric", "feature", "operator", "threshold", "points", "level"}
    optional = {"window", "consecutive", "min_span_seconds", "max_gap_seconds", "daily", "window_days", "matches", "points_per_unit"}
    if not isinstance(rule, dict) or not required <= set(rule) or set(rule) - required - optional:
        raise ValueError("A rule has missing or unknown fields")
    if not isinstance(rule["id"], str) or not rule["id"].strip() or rule["metric"] not in known_metrics:
        raise ValueError("Rules require an ID and a supported metric")
    if rule["feature"] not in FEATURES or rule["operator"] not in OPERATORS:
        raise ValueError("Unsupported feature or comparison operator")
    if rule["metric"] in BOOLEAN_METRICS and rule["feature"] not in {"hours_since_true", "missed_mission_days"} and not (rule["feature"] == "value" and rule["operator"] == "eq" and isinstance(rule["threshold"], bool)):
        raise ValueError("Boolean metrics require value/eq with a boolean threshold")
    if (rule["metric"] == "symptoms") != (rule["feature"] in {"count", "contains_any"}):
        raise ValueError("Symptom lists require count; numeric and boolean metrics do not")
    if rule["metric"] in NUMERIC_RULES and isinstance(rule["threshold"], bool):
        raise ValueError("Numeric metrics require numeric thresholds")
    threshold = rule["threshold"]
    if isinstance(threshold, bool):
        if rule["feature"] != "value" or rule["operator"] != "eq":
            raise ValueError("Boolean thresholds require value/eq")
    elif not _finite(threshold):
        raise ValueError("threshold must be finite")
    if not _finite(rule["points"]) or not 0 < rule["points"] <= 100 or type(rule["level"]) is not int or rule["level"] not in (1, 2, 3):
        raise ValueError("Triggered rules require positive points and a level from 1 to 3")
    if type(rule.get("window", 3)) is not int or not 2 <= rule.get("window", 3) <= 1000:
        raise ValueError("window must be between 2 and 1000 observations")
    streak = rule.get("consecutive", 1)
    if type(streak) is not int or not 1 <= streak <= 100:
        raise ValueError("consecutive must be between 1 and 100 observations")
    for field in ("min_span_seconds", "max_gap_seconds"):
        if field in rule and (not _finite(rule[field]) or rule[field] < 0 or (field == "max_gap_seconds" and rule[field] == 0)):
            raise ValueError(field + " must be finite and nonnegative (positive for max_gap_seconds)")
    if streak == 1 and rule.get("min_span_seconds", 0) > 0:
        raise ValueError("A positive minimum span requires more than one observation")

    if "daily" in rule and type(rule["daily"]) is not bool:
        raise ValueError("daily must be boolean")
    if "window_days" in rule and (rule["feature"] not in {"baseline_change", "baseline_change_pct", "mad_deviation"}
            or type(rule["window_days"]) is not int or not 2 <= rule["window_days"] <= 365):
        raise ValueError("window_days requires a baseline feature and 2 to 365 days")
    if rule["feature"] == "contains_any":
        if not isinstance(rule.get("matches"), list) or not rule["matches"] or any(
                not isinstance(value, str) or not value.strip() for value in rule["matches"]):
            raise ValueError("contains_any requires symptom names in matches")
    elif "matches" in rule:
        raise ValueError("matches is only supported for contains_any")
    if rule["feature"] in {"hours_since_true", "missed_mission_days"}:
        if rule["metric"] not in BOOLEAN_METRICS or isinstance(threshold, bool) or rule.get("consecutive", 1) != 1:
            raise ValueError("Elapsed/mission features require a boolean metric, numeric threshold, and no streak")
        if rule["feature"] == "missed_mission_days" and rule["metric"] != "exercise_logged":
            raise ValueError("missed_mission_days requires exercise_logged")
    if "points_per_unit" in rule and (type(rule["points_per_unit"]) is not bool or rule["feature"] != "missed_mission_days"):
        raise ValueError("points_per_unit is supported only for missed_mission_days")
