"""Evaluate explicit point-based policies against clean, timestamped history."""

import hashlib
import operator
from datetime import datetime, timezone

from ingest_validate.validation import json_string, utc_string
from .features import feature_value
from .policy import COLORS, DOMAINS, policy_digest, validate_policy


COMPARISONS = {"gt": operator.gt, "gte": operator.ge, "lt": operator.lt, "lte": operator.le, "eq": operator.eq}


def _timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    utc_string(parsed)
    return parsed


def _history(history, astronaut_id, policy, as_of):
    needed = {rule["metric"] for domain in policy["domains"].values() for rule in domain["rules"]}
    chosen = {}
    excluded_future = 0
    for observation in history:
        if not isinstance(observation, dict):
            raise ValueError("Assessment history must contain normalized observation objects")
        metric = observation.get("metric")
        source = policy.get("metric_sources", {}).get(metric, policy["source"])
        if observation.get("astronaut_id") != astronaut_id or metric not in needed or observation.get("source") != source:
            continue
        captured = _timestamp(observation["captured_at"])
        if captured > as_of:
            excluded_future += 1
            continue
        if policy["simulation_only"] and observation.get("context", {}).get("simulated") is not True:
            raise ValueError("This policy is restricted to explicitly simulated observations")
        normalized = {**observation, "captured_at": utc_string(captured)}
        key = (metric, source, normalized["captured_at"])
        if key in chosen and json_string(chosen[key]) != json_string(normalized):
            raise ValueError("Conflicting measurements in assessment history")
        chosen[key] = normalized
    ordered = [chosen[key] for key in sorted(chosen, key=lambda key: (key[2], key[0], key[1]))]
    streams = {}
    for observation in ordered:
        streams.setdefault(observation["metric"], []).append(observation)
    return ordered, streams, excluded_future


def _rule_result(rule, readings, policy, as_of):
    result = {"rule_id": rule["id"], "metric": rule["metric"],
              "source": policy.get("metric_sources", {}).get(rule["metric"], policy["source"]),
              "available": False, "triggered": None, "points": None, "level": None, "features": []}
    if not readings:
        return {**result, "reason": "missing_metric"}
    latest = readings[-1]
    result.update({"observed_value": latest["value"], "captured_at": latest["captured_at"]})
    if (as_of - _timestamp(latest["captured_at"])).total_seconds() > policy["max_age_seconds"]:
        return {**result, "reason": "stale_metric"}
    streak = rule.get("consecutive", 1)
    if len(readings) < streak:
        return {**result, "reason": "insufficient_streak"}
    recent = readings[-streak:]
    times = [_timestamp(item["captured_at"]) for item in recent]
    if (times[-1] - times[0]).total_seconds() < rule.get("min_span_seconds", 0):
        return {**result, "reason": "insufficient_streak_span"}
    if "max_gap_seconds" in rule and any((b - a).total_seconds() > rule["max_gap_seconds"] for a, b in zip(times, times[1:])):
        return {**result, "reason": "sampling_gap"}
    # We evaluate every point in a streak against its own preceding baseline,
    # rather than reuse the newest baseline for older observations.
    features = [feature_value(readings, index, rule["feature"], rule.get("window", 3))
                for index in range(len(readings) - streak, len(readings))]
    result["features"] = features
    unavailable = next((value for value in features if value["value"] is None), None)
    if unavailable is not None:
        return {**result, "reason": unavailable["reason"]}
    values = [value["value"] for value in features]
    if any(isinstance(value, bool) != isinstance(rule["threshold"], bool) for value in values):
        return {**result, "reason": "incompatible_rule_value"}
    triggered = all(COMPARISONS[rule["operator"]](value, rule["threshold"]) for value in values)
    return {**result, "available": True, "triggered": triggered,
            "points": rule["points"] if triggered else 0, "level": rule["level"] if triggered else 0}


def assess_history(history, astronaut_id, policy, *, as_of=None):
    """Return reproducible domain and metric scores, preserving unknown states.

    Scores are configured points, not probabilities. No thresholds or medical
    interpretation are inferred from data-quality validation bounds.
    """
    policy = validate_policy(policy)
    if not isinstance(astronaut_id, str) or not astronaut_id.strip():
        raise ValueError("astronaut_id is required")
    clock = as_of if as_of is not None else datetime.now(timezone.utc)
    assessed_at = utc_string(clock)
    ordered, streams, future_count = _history(history, astronaut_id, policy, clock)
    domains, metric_rules = {}, {}
    for name in DOMAINS:
        definition = policy["domains"][name]
        rules = [_rule_result(rule, streams.get(rule["metric"], []), policy, clock) for rule in definition["rules"]]
        for result in rules:
            metric_rules.setdefault(result["metric"], []).append(result)
        known_points = sum(result["points"] or 0 for result in rules)
        complete = all(result["available"] for result in rules)
        score = min(100, known_points) if complete else None
        level = max(band["level"] for band in definition["bands"] if score >= band["min_points"]) if complete else None
        # We never label a domain green merely because a baseline or required
        # metric is missing. We retain the unavailable rules for explanation.
        domains[name] = {"risk_score": score, "known_points": known_points, "level": level,
                         "status": COLORS[level] if level is not None else "unknown",
                         "data_status": "complete" if complete else "insufficient_data", "rules": rules}
    metrics = {}
    for metric, rules in metric_rules.items():
        known = [rule["level"] for rule in rules if rule["available"]]
        # We preserve a known warning even when another rule is unavailable,
        # while a partial set of non-triggered rules is not proof of green.
        level = max(known) if known and (max(known) > 0 or len(known) == len(rules)) else None
        readings = streams.get(metric, [])
        metrics[metric] = {"value": readings[-1]["value"] if readings else None,
                           "source": readings[-1]["source"] if readings else None,
                           "captured_at": readings[-1]["captured_at"] if readings else None,
                           "level": level, "status": COLORS[level] if level is not None else "unknown",
                           "data_complete": len(known) == len(rules)}
    known_levels = [domain["level"] for domain in domains.values() if domain["level"] is not None]
    overall = max(known_levels) if known_levels and (max(known_levels) > 0 or len(known_levels) == len(DOMAINS)) else None
    digest = policy_digest(policy)
    input_digest = hashlib.sha256(json_string(ordered).encode()).hexdigest()
    assessment_key = hashlib.sha256(json_string([astronaut_id, digest, assessed_at, input_digest]).encode()).hexdigest()
    return {"schema_version": "astrocrates.assessment.v1", "assessment_key": assessment_key,
            "astronaut_id": astronaut_id, "assessed_at": assessed_at, "policy_id": policy["policy_id"],
            "policy_digest": digest, "policy_purpose": policy["purpose"], "simulation_only": policy["simulation_only"],
            "score_type": "configured_points", "input_digest": input_digest, "observation_count": len(ordered),
            "excluded_future_observations": future_count, "domains": domains, "metrics": metrics,
            "overall_level": overall, "overall_status": COLORS[overall] if overall is not None else "unknown",
            "assessment_complete": all(domain["level"] is not None for domain in domains.values())}
