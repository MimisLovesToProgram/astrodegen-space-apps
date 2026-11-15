
"""
assessmentEngine.py

STEP 3 - Astronaut Health Risk Assessment Engine

! Assess vs Normal range

Responsibilities:
1. Receive validated telemetry history from Step 2.
2. Evaluate the four physiological domains.

3. Calculate risk scores (0-100).
4. Identify triggered risk rules.
5. Classify each domain as GREEN, YELLOW, ORANGE, or RED.
6. Return structured assessment results.

This module does NOT generate sensor readings, validate ingestion,
create action cards, or send escalations.
"""

import logging
from datetime import datetime
from statistics import mean

from step2_config import RISK_MODELS

logger = logging.getLogger(__name__)

# PocketBase access and the sensor_readings value encoding live in
# DataPopulateEngine; this module reuses them so both engines agree on
# how readings are stored and read back.
from DataPopulateEngine import (
    PocketBaseStore,
    _deserialize_value,
)


# ---------------------------------------------------------
# SECTION 1: Configuration
# ---------------------------------------------------------

# Severity boundaries are configurable demonstration values.
# Each domain's own trigger_at value determines its GREEN boundary.

YELLOW_OFFSET = 0
ORANGE_OFFSET = 15
RED_OFFSET = 30

METRIC_ALIASES = {
    "hr_resting": "hr",
    "sleep_h": "sleep_h",
    "temp_c": "temp_c",
}


# ---------------------------------------------------------
# SECTION 2: Helper functions
# ---------------------------------------------------------

def get_value(reading, metric):
    """Retrieve a metric, supporting legacy field aliases."""

    field = METRIC_ALIASES.get(metric, metric)

    if field in reading:
        return reading[field]

    return reading.get(metric)


def parse_timestamp(reading):
    """Convert an ISO timestamp into a datetime object."""

    timestamp = reading.get("timestamp")

    if not timestamp:
        return None

    return datetime.fromisoformat(
        timestamp.replace("Z", "+00:00")
    )


def compare(value, condition):
    """Evaluate basic numerical comparison operators."""

    if value is None:
        return False

    op = condition["op"]
    target = condition.get("value")

    if op == "lt":
        return value < target

    if op == "lte":
        return value <= target

    if op == "gt":
        return value > target

    if op == "gte":
        return value >= target

    if op == "eq":
        return value == target

    if op == "between":
        return target[0] <= value <= target[1]

    return False


def get_baseline(history, index, metric, days):
    """
    Calculate the average of previous readings.

    The current reading is excluded from the baseline.
    """

    previous = history[max(0, index - days):index]

    values = [
        get_value(reading, metric)
        for reading in previous
    ]

    values = [
        float(value)
        for value in values
        if isinstance(value, (int, float))
    ]

    if not values:
        return None

    return mean(values)


# ---------------------------------------------------------
# SECTION 3: Evaluate individual conditions
# ---------------------------------------------------------

def evaluate_condition(history, index, rule):
    """Evaluate one risk rule against a telemetry reading."""

    reading = history[index]

    metric = rule["metric"]
    condition = rule["condition"]

    op = condition["op"]
    value = get_value(reading, metric)

    # Symptom detection
    if op == "contains_any":

        symptoms = value or []

        if isinstance(symptoms, str):
            symptoms = [symptoms]

        return any(
            symptom in symptoms
            for symptom in condition["value"]
        )

    # HRV percentage decrease compared with baseline
    if op == "pct_drop_vs_baseline":

        baseline = get_baseline(
            history,
            index,
            metric,
            condition["baseline_days"]
        )

        if baseline is None or baseline == 0 or value is None:
            return False

        percentage_drop = (
            (baseline - value) / baseline
        ) * 100

        return percentage_drop > condition["value"]

    # Resting heart rate above baseline
    if op == "above_baseline_by":

        baseline = get_baseline(
            history,
            index,
            metric,
            condition["baseline_days"]
        )

        if baseline is None or value is None:
            return False

        return value > baseline + condition["value"]

    # Activity percentage below target
    if op == "activity_below_pct_of_target":

        activity = reading.get("activity_pct_of_target")

        if activity is None:
            return False

        return activity < condition["value"]

    # Ordinary numerical comparisons
    return compare(value, condition)


# ---------------------------------------------------------
# SECTION 4: Historical rule evaluation
# ---------------------------------------------------------

def evaluate_rule(history, rule):
    """
    Evaluate a complete rule, including historical conditions.

    Returns:
        points: Points contributed by the rule.
        matched: Whether the rule was triggered.
    """

    condition = rule["condition"]
    op = condition["op"]

    # Bone-loss rule: +2 points per mission day
    # without a resistance exercise log.
    if op == "false_streak_per_day":

        missed_days = sum(
            1 for reading in history
            if get_value(reading, "exercise_logged") is False
        )

        points = missed_days * rule["points"]

        return min(points, 100), points > 0

    # Bone-loss rule: more than 14 days since exercise
    if op == "days_since":

        exercise_days = [
            reading.get("mission_day")
            for reading in history
            if get_value(reading, "exercise_logged") is True
        ]

        if not exercise_days:
            return 0, False

        current_day = max(
            reading.get("mission_day", 0)
            for reading in history
        )

        last_exercise_day = max(exercise_days)

        days_since = current_day - last_exercise_day

        matched = days_since > condition["value"]

        return (
            rule["points"] if matched else 0,
            matched
        )

    # Evaluate the latest reading
    latest_index = len(history) - 1

    streak_days = condition.get("streak_days", 1)

    # A streak requires the condition to hold
    # for the specified number of consecutive readings.
    if streak_days > 1:

        if len(history) < streak_days:
            return 0, False

        start = len(history) - streak_days

        matched = all(
            evaluate_condition(history, i, rule)
            for i in range(start, len(history))
        )

    # Ordinary single-reading or baseline-based rule
    else:

        matched = evaluate_condition(
            history,
            latest_index,
            rule
        )

    return (
        rule["points"] if matched else 0,
        matched
    )


# ---------------------------------------------------------
# SECTION 5: Risk classification
# ---------------------------------------------------------

def classify_risk(score, trigger_at):
    """
    Classify a domain's risk score.

    These severity offsets are configurable demo values.
    """

    if score < trigger_at:
        return "GREEN"

    if score >= trigger_at + RED_OFFSET:
        return "RED"

    if score >= trigger_at + ORANGE_OFFSET:
        return "ORANGE"

    return "YELLOW"


# ---------------------------------------------------------
# SECTION 6: Assess individual domain
# ---------------------------------------------------------

def assess_domain(domain, history):
    """Calculate the risk score for one health domain."""

    model = RISK_MODELS[domain]

    score = 0
    matched_rules = []

    for rule in model["rules"]:

        points, matched = evaluate_rule(
            history,
            rule
        )

        score += points

        if matched:

            matched_rules.append({
                "metric": rule["metric"],
                "description": rule["description"],
                "points": points
            })

    # Risk scores are limited to the 0-100 scale.
    score = min(score, 100)

    trigger_at = model["trigger_at"]

    risk_level = classify_risk(
        score,
        trigger_at
    )

    triggered = score >= trigger_at

    return {
        "domain": domain,
        "risk_score": score,
        "risk_level": risk_level,
        "triggered": triggered,

        "trigger_at": trigger_at,

        "trigger_message": (
            model["trigger_message"]
            if triggered else None
        ),

        "matched_rules": matched_rules
    }


# ---------------------------------------------------------
# SECTION 7: Main assessment engine
# ---------------------------------------------------------

def assess_astronaut(telemetry_history, crew_id=None):
    """
    Assess all four health domains for one astronaut.

    Args:
        telemetry_history: Validated historical telemetry packets.
        crew_id: Astronaut identifier, e.g. 'a', 'b', or 'c'.

    Returns:
        Structured assessment results for all four domains.
    """

    if not telemetry_history:
        raise ValueError("Telemetry history is empty.")

    # Separate astronauts when the input contains multiple crews.
    if crew_id is not None:

        history = [
            reading
            for reading in telemetry_history
            if reading.get("crew_id") == crew_id
        ]

    else:

        crew_ids = {
            reading.get("crew_id")
            for reading in telemetry_history
        }

        if len(crew_ids) > 1:
            raise ValueError(
                "Multiple astronauts found. Specify crew_id."
            )

        history = list(telemetry_history)

    if not history:
        raise ValueError(
            f"No telemetry found for astronaut {crew_id}."
        )

    # Sort chronologically.
    history.sort(
        key=lambda reading: (
            reading.get("mission_day", 0),
            parse_timestamp(reading)
            or datetime.min
        )
    )

    # Assess each physiological domain independently.
    results = {
        domain: assess_domain(domain, history)
        for domain in RISK_MODELS
    }

    for domain, result in results.items():
        logger.debug(
            "crew %s domain %s: score=%d level=%s rules=%s",
            crew_id or history[-1].get("crew_id"), domain,
            result["risk_score"], result["risk_level"],
            [rule["metric"] for rule in result["matched_rules"]])

    # Identify the highest-priority risk.
    priority = [
        "cardiovascular",
        "immune",
        "behavioral",
        "bone_loss"
    ]

    highest_risk = max(
        priority,
        key=lambda domain: (
            results[domain]["risk_score"],
            -priority.index(domain)
        )
    )

    return {
        "crew_id": crew_id or history[-1].get("crew_id"),

        "mission_day": history[-1].get("mission_day"),

        "assessed_at": datetime.now().astimezone().isoformat(),

        "overall_status": results[highest_risk]["risk_level"],

        "highest_risk_domain": highest_risk,

        "domain_assessments": results
    }


# ---------------------------------------------------------
# SECTION 8: PocketBase read/write stages
#
# These functions let callers run each stage manually:
#   load_history()      - read sensor_readings, group into daily packets
#   assess_astronaut()  - pure scoring (sections 1-7)
#   save_assessment()   - post domain_assessments records
#   assess_crew()       - all three stages for one crew member
#   assess_all()        - every crew member
# ---------------------------------------------------------

def load_history(crew_id, store):
    """Read sensor_readings for one crew member and regroup them into
    per-day telemetry packets, the shape assess_astronaut() expects.

    Each packet carries crew_id, mission_day, timestamp, and one key per
    sensor_readings.select metric.
    """
    astronaut_id = store.astronaut_id(crew_id)
    records = []
    page = 1
    while True:
        batch = store.client.request(
            "GET", "/api/collections/sensor_readings/records",
            query={
                "filter": f'astronaut="{astronaut_id}"',
                "sort": "captured_at,id", "perPage": 500, "page": page,
                "skipTotal": "true",
            },
        )["items"]
        records.extend(batch)
        if len(batch) < 500:
            break
        page += 1

    logger.info("Loaded %d sensor_readings for crew %s",
                len(records), crew_id)

    days = {}
    for record in records:
        if not record.get("captured_at") or not record.get("select"):
            continue
        day = record.get("mission_day")
        key = day if day is not None else record["captured_at"][:10]
        packet = days.get(key)
        if packet is None:
            packet = days[key] = {
                "crew_id": crew_id,
                "mission_day": day if day is not None else 0,
                "timestamp": record["captured_at"],
            }
        elif record["captured_at"] < packet["timestamp"]:
            packet["timestamp"] = record["captured_at"]
        packet[record["select"]] = _deserialize_value(
            record["select"], record["value"])

    history = sorted(
        days.values(),
        key=lambda packet: (packet["mission_day"], packet["timestamp"]),
    )
    logger.info("Grouped crew %s readings into %d daily packets "
                "(mission days %s)",
                crew_id, len(history),
                sorted({p["mission_day"] for p in history}))
    return history


def save_assessment(crew_id, assessment, store):
    """Post one domain_assessments record per domain to PocketBase."""
    astronaut_id = store.astronaut_id(crew_id)
    for domain, result in assessment["domain_assessments"].items():
        details = {
            "matched_rules": result["matched_rules"],
            "triggered": result["triggered"],
            "trigger_at": result["trigger_at"],
            "trigger_message": result["trigger_message"],
            "assessed_at": assessment["assessed_at"],
            "overall_status": assessment["overall_status"],
            "highest_risk_domain": assessment["highest_risk_domain"],
        }
        store.client.request(
            "POST", "/api/collections/domain_assessments/records",
            {
                "astronaut": astronaut_id,
                "domain": domain,
                "domain_status": result["risk_level"].lower(),
                "risk_score": result["risk_score"],
                "details": details,
            },
        )
        logger.debug("Posted %s assessment for crew %s: %s score=%d",
                     domain, crew_id, result["risk_level"].lower(),
                     result["risk_score"])


def assess_crew(crew_id, store=None, post=True):
    """Run all stages for one crew member.

    Reads their stored readings, scores all four domains, and posts the
    results. Set post=False to compute without writing.
    """
    store = store or PocketBaseStore.from_environment()
    logger.info("Assessing crew %s (post=%s)", crew_id, post)
    history = load_history(crew_id, store)
    assessment = assess_astronaut(history, crew_id=crew_id)
    logger.info(
        "Crew %s assessed: overall=%s highest_risk=%s day=%s",
        crew_id, assessment["overall_status"],
        assessment["highest_risk_domain"], assessment["mission_day"])
    if post:
        save_assessment(crew_id, assessment, store)
        logger.info("Posted %d domain_assessments records for crew %s",
                    len(assessment["domain_assessments"]), crew_id)
    return assessment


def assess_all(store=None, post=True, crew_ids=("a", "b", "c")):
    """Assess every crew member; crews without readings are skipped."""
    store = store or PocketBaseStore.from_environment()
    results = {}
    for crew_id in crew_ids:
        try:
            results[crew_id] = assess_crew(crew_id, store, post=post)
        except ValueError as error:
            logger.warning("Skipping crew %s: %s", crew_id, error)
            results[crew_id] = {"error": str(error)}
    return results


# ---------------------------------------------------------
# SECTION 9: Example execution
# ---------------------------------------------------------

if __name__ == "__main__":

    import json

    # Read stored readings, assess, and post results for every crew.
    print(json.dumps(assess_all(), indent=4))
