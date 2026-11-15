
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

from datetime import datetime
from statistics import mean

from step2_config import RISK_MODELS


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
# SECTION 8: Example execution
# ---------------------------------------------------------

if __name__ == "__main__":

    import json

    # Example: Load validated telemetry packets.
    with open("validated_readings.json", "r") as file:
        telemetry = json.load(file)

    # Assess one astronaut.
    assessment = assess_astronaut(
        telemetry_history=telemetry,
        crew_id="a"
    )

    print("\n===== ASTRONAUT RISK ASSESSMENT =====")

    print(
        json.dumps(
            assessment,
            indent=4
        )
    )
