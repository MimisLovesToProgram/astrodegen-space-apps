"""Structured health-monitoring data parsed from
docs/team-health-rules.md.

This module holds the telemetry thresholds, domain mappings, and risk
assessment rules used by the assessment engine. It is data only; all
evaluation logic lives in assessment/engine.py and assessment/temporal.py.
"""

# ---------------------------------------------------------------------------
# Section 1: Biometric & behavioral telemetry thresholds
#
# `input_type` is "sensor" for automated telemetry and "user" for
# self-reported logs. Ranges are given as (min, max) tuples; a bound of
# None means unbounded on that side. `alert` uses the same shape.
# ---------------------------------------------------------------------------

SENSOR_THRESHOLDS = {
    "hr_resting": {
        "input_type": "sensor",
        "unit": "bpm",
        "normal": (50, 100),
        "watch": [(100, 110), (45, 50)],
        "alert": [("gt", 120), ("lt", 45)],
    },
    "hrv": {
        "input_type": "sensor",
        "unit": "ms",
        "normal": (40, 80),
        "watch": [(30, 40)],
        "alert": [("lt", 30)],
    },
    "spo2": {
        "input_type": "sensor",
        "unit": "%",
        "normal": (95, 100),
        "watch": [(92, 95)],
        "alert": [("lt", 92)],
    },
    "temp_c": {
        "input_type": "sensor",
        "unit": "degC",
        "normal": (36.0, 37.5),
        "watch": [(37.5, 38.5)],
        "alert": [("gte", 38.6), ("lt", 35.5)],
    },
    "radiation_msv_cumulative": {
 "input_type": "sensor",
        "unit": "mSv",
        "limit": 600,  # cumulative mission limit
        "normal": (None, 600),
        "watch": [("gte", 360)],   # 60% of limit
        "alert": [("gte", 600)],   # >= limit
    },
    "sleep_h": {
        "input_type": "user",
        "unit": "h",
        "normal": (7, 9),
        "watch": [(6, 7)],
        "alert": [("lt", 6)],
    },
    "sleep_quality": {
        "input_type": "user",
        "scale": (1, 5),
        "normal": (3, 5),
        "watch": [2],
        "alert": [1],
    },
    "mood": {
        "input_type": "user",
        "scale": (1, 5),
        "normal": (3, 5),
        "watch": [2],
        "alert": [1],
    },
    "symptoms": {
        "input_type": "user",
        "normal": "empty",
        "watch": "1 symptom",
        "alert": ">=2 symptoms",
    },
    "exercise_logged": {
        "input_type": "user",
        "normal": "true most days",
        "watch": "3+ days false",
        "alert": "3+ days false",
    },
    "social_interaction": {
        "input_type": "user",
        "normal": "true most days",
        "watch": "2 days false",
        "alert": "3+ days false",
    },
}

# ---------------------------------------------------------------------------
# Section 2: Physiological domains & spaceflight rationale
# ---------------------------------------------------------------------------

DOMAIN_MAPPINGS = {
    "immune": ["sleep", "sleep_quality", "temp", "spo2", "symptoms"],
    "cardiovascular": ["hr", "hrv", "exercise", "spo2"],
    "behavioral": ["mood", "sleep_quality", "social_interaction", "sleep_h"],
    "bone_loss": ["exercise_logged", "mission_day"],
}

DOMAIN_RATIONALE = {
    "immune": "Space radiation, sleep debt, and stress suppress immune function.",
    "cardiovascular": "Microgravity deconditions the heart and causes fluid shifts.",
    "behavioral": "Isolation causes sleep disruption and mood decline.",
    "bone_loss": "Astronauts experience 1-1.5% bone loss per month in "
                 "weight-bearing bones without countermeasures.",
}

# ---------------------------------------------------------------------------
# Section 3: Risk assessment models (0-100 scale)
#
# Each rule is a dict with:
#   points      - score contribution
#   metric      - telemetry field the rule evaluates (None for special cases)
#   condition   - machine-readable predicate, e.g. {"op": "lt", "value": 6,
#                 "streak_days": 3}
#   description - human-readable summary of the condition
#   trigger     - escalation message when the domain score reaches `trigger_at`
#
# Threshold comparison ops: lt, lte, gt, gte, eq, between.
# `streak_days` means the condition must hold for N consecutive days.
# `window_days` means the condition is evaluated over a rolling N-day window.
# ---------------------------------------------------------------------------

RISK_MODELS = {
    "immune": {
        "trigger_at": 60,
        "trigger_message": "Elevated - rest, hydrate, notify personnel",
        "rules": [
            {"points": 30, "metric": "sleep_h",
             "condition": {"op": "lt", "value": 6, "streak_days": 3},
             "description": "sleep_h < 6h for 3+ days"},
            {"points": 25, "metric": "spo2",
             "condition": {"op": "lt", "value": 95},
             "description": "spo2 < 95%"},
            {"points": 20, "metric": "temp_c",
             "condition": {"op": "gt", "value": 37.5},
             "description": "temp_c > 37.5C"},
            {"points": 15, "metric": "symptoms",
             "condition": {"op": "contains_any",
                           "value": ["sore throat", "fatigue"]},
             "description": 'symptom "sore throat" or "fatigue" checked'},
            {"points": 10, "metric": "hrv",
             "condition": {"op": "pct_drop_vs_baseline",
                           "value": 20, "baseline_days": 7},
             "description": "hrv dropped >20% vs 7-day baseline"},
        ],
    },
    "bone_loss": {
        "trigger_at": 50,
        "trigger_message": "Run bone density protocol, mandatory "
                           "resistance session today",
        "rules": [
            {"points": 2, "metric": "exercise_logged",
             "condition": {"op": "false_streak_per_day"},
             "description": "+2 points per mission day without "
                            "resistance exercise log"},
            {"points": 20, "metric": "exercise_logged",
             "condition": {"op": "days_since", "value": 14},
             "description": ">14 days since last exercise session"},
        ],
    },
    "cardiovascular": {
        "trigger_at": 55,
        "trigger_message": "Cardio deconditioning - schedule exercise log "
                           "for ground review",
        "rules": [
            {"points": 25, "metric": "hr_resting",
             "condition": {"op": "above_baseline_by", "value": 15,
                           "baseline_days": 7, "streak_days": 2},
             "description": "resting hr > baseline +15bpm for 2 days"},
            {"points": 20, "metric": "hrv",
             "condition": {"op": "pct_drop_vs_baseline", "value": 25,
                           "baseline_days": 7},
             "description": "hrv < baseline -25%"},
            {"points": 15, "metric": "activity_pct_target",
             "condition": {"op": "activity_below_pct_of_target", "value": 50},
             "description": "activity < 50% of target"},
        ],
    },
    "behavioral": {
        "trigger_at": 50,
        "trigger_message": "Check in with crew, schedule ground call, "
                           "log mood journal",
        "rules": [
            {"points": 20, "metric": "mood",
             "condition": {"op": "lte", "value": 2, "streak_days": 2},
             "description": "mood <= 2 for 2+ days"},
            {"points": 20, "metric": "sleep_quality",
             "condition": {"op": "lte", "value": 2},
             "description": "sleep_quality <= 2"},
            {"points": 15, "metric": "social_interaction",
             "condition": {"op": "false_streak", "value": 48, "unit": "hours"},
             "description": "no social_interaction logged in 48h"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Section 4: Escalation queue prioritization
# ---------------------------------------------------------------------------

DOMAIN_PRIORITY = ["cardiovascular", "immune", "behavioral", "bone_loss"]
SEVERITY_ORDER = ["red", "orange", "yellow"]  # highest first

DOMAINS = list(RISK_MODELS.keys())
