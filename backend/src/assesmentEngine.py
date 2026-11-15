"""Step 3 assessment engine.

Bootstraps the synthetic sensor generator, parses packets through the
ingest_validate adapter/validator, stores accepted readings in the local
PocketBase sensor_readings collection, scores each crew member against the
rules in health_data.py, and posts one domain_assessments record per domain.

Run from the repository root:

    PYTHONPATH=backend/src python3 backend/src/assesmentEngine.py
    PYTHONPATH=backend/src python3 backend/src/assesmentEngine.py --mode noise --ticks 5
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# The ingestion pipeline lives in the repository's src/ package; this file
# lives in backend/src/, so both directories are added explicitly.
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import health_data
from astrocrates import sensor_batches
from ingest_validate.adapters import sensor_observations
from ingest_validate.config import connection_settings
from ingest_validate.pipeline import simulated_mission
from ingest_validate.pocketbase import PocketBaseTelemetry
from ingest_validate.validation import validate_observation


# The parser emits normalized metric names; health_data thresholds and the
# PocketBase sensor_type field use a slightly different vocabulary.
METRIC_ALIASES = {
    "hrv_rmssd": "hrv",
    "hr": "hr_resting",
    "sleep": "sleep_h",
    "temp": "temp_c",
    "exercise": "exercise_logged",
}

# DOMAIN_MAPPINGS uses shorthand names; map them onto threshold keys.
DOMAIN_METRIC_ALIASES = {
    "hr": "hr_resting",
    "hrv": "hrv",
    "sleep": "sleep_h",
    "temp": "temp_c",
    "exercise": "exercise_logged",
    "spo2": "spo2",
    "symptoms": "symptoms",
    "mood": "mood",
    "sleep_quality": "sleep_quality",
    "social_interaction": "social_interaction",
}

# Validated observation metric -> sensor_readings.sensor_type select value.
# mission_day is not a sensor_type; it is stored in its own number field.
SENSOR_TYPE_BY_METRIC = {
    "hr_resting": "hr_resting",
    "hrv_rmssd": "hrv",
    "spo2": "spo2",
    "temp_c": "temp_c",
    "radiation_msv_cumulative": "radiation_msv_cumulative",
    "sleep_h": "sleep_h",
    "sleep_quality": "sleep_quality",
    "mood": "mood",
    "symptoms": "symptoms",
    "exercise_logged": "exercise_logged",
    "social_interaction": "social_interaction",
}


def _parse_time(value):
    text = str(value).replace(" ", "T").replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _epoch(value):
    return _parse_time(value).timestamp()


def _pb_datetime(value):
    """Format an ISO timestamp the way PocketBase date fields expect."""
    parsed = _parse_time(value)
    return (parsed.strftime("%Y-%m-%d %H:%M:%S.")
            + f"{parsed.microsecond // 1000:03d}Z")


def _serialize_value(value):
    """sensor_readings.value is a text field; keep a reversible encoding."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return json.dumps(value)
    return str(value)


def _deserialize_value(sensor_type, raw):
    if sensor_type == "symptoms":
        return json.loads(raw)
    if sensor_type in ("exercise_logged", "social_interaction"):
        return raw == "true"
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


def build_series(history):
    """Group clean observations into per-metric (time, value) series.

    Returns {canonical_metric: [(datetime, value), ...]} oldest first.
    """
    series = {}
    for observation in history:
        metric = METRIC_ALIASES.get(observation["metric"], observation["metric"])
        series.setdefault(metric, []).append(
            (_parse_time(observation["captured_at"]), observation["value"])
        )
    for points in series.values():
        points.sort(key=lambda point: point[0])
    return series


def _values(series, metric):
    return [value for _, value in series.get(metric, [])]


def _latest(series, metric):
    values = _values(series, metric)
    return values[-1] if values else None


def _compare(op, value, threshold):
    if op == "lt":
        return value < threshold
    if op == "lte":
        return value <= threshold
    if op == "gt":
        return value > threshold
    if op == "gte":
        return value >= threshold
    if op == "eq":
        return value == threshold
    if op == "between":
        return threshold[0] <= value <= threshold[1]
    raise ValueError(f"Unsupported comparison op: {op}")


def _band_matches(value, band):
    """Match a scalar against one watch/alert band entry.

    Bands are either (low, high) inclusive ranges, (op, bound) comparisons,
    or plain numbers meaning exact equality (Likert scores).
    """
    if isinstance(band, tuple) and len(band) == 2 and isinstance(band[0], str):
        return _compare(band[0], value, band[1])
    if isinstance(band, tuple):
        return band[0] <= value <= band[1]
    return value == band


def _in_threshold_band(value, spec):
    """Classify a value against a SENSOR_THRESHOLDS entry."""
    if value is None:
        return "missing"

    # Non-numeric specs: symptoms is a list, exercise/social are booleans
    # whose streak rules live in RISK_MODELS rather than scalar bands.
    normal = spec.get("normal")
    if isinstance(normal, str):
        if normal == "empty" and isinstance(value, list):
            count = len(value)
            return "normal" if count == 0 else ("watch" if count == 1 else "alert")
        if isinstance(value, bool):
            return "normal" if value else "watch"
        return "normal"

    if any(_band_matches(value, band) for band in spec.get("alert", [])):
        return "alert"
    if any(_band_matches(value, band) for band in spec.get("watch", [])):
        return "watch"
    low, high = spec["normal"]
    if (low is None or value >= low) and (high is None or value <= high):
        return "normal"
    # Outside the normal range but not in an explicit band still counts as
    # watch so nothing silently passes.
    return "watch"


def metric_statuses(series, domain):
    """Latest-value status for every mapped metric in a domain."""
    statuses = {}
    for shorthand in health_data.DOMAIN_MAPPINGS[domain]:
        metric = DOMAIN_METRIC_ALIASES.get(shorthand, shorthand)
        if metric == "mission_day" or metric not in health_data.SENSOR_THRESHOLDS:
            continue
        statuses[metric] = _in_threshold_band(
            _latest(series, metric), health_data.SENSOR_THRESHOLDS[metric]
        )
    return statuses


def _baseline(values, count):
    """Mean of up to `count` values preceding the latest one."""
    prior = values[:-1][-count:]
    return sum(prior) / len(prior) if prior else None


def _rule_matches(condition, series, metric):
    """Evaluate one risk rule's condition against the metric series."""
    op = condition["op"]
    values = _values(series, metric)
    points_series = series.get(metric, [])

    if op in ("lt", "lte", "gt", "gte", "eq", "between"):
        if not values:
            return False, 0
        threshold = condition["value"]
        streak = condition.get("streak_days", 1)
        # One observation per mission day in the story data, so the last
        # `streak` values approximate consecutive daily readings.
        window = values[-streak:]
        return all(_compare(op, v, threshold) for v in window), 0

    if op == "contains_any":
        latest = _latest(series, metric)
        if not isinstance(latest, list):
            return False, 0
        return any(item in latest for item in condition["value"]), 0

    if op == "pct_drop_vs_baseline":
        if len(values) < 2:
            return False, 0
        baseline = _baseline(values, condition.get("baseline_days", 7))
        if baseline is None or baseline == 0:
            return False, 0
        drop_pct = (baseline - values[-1]) / baseline * 100
        return drop_pct >= condition["value"], 0

    if op == "above_baseline_by":
        baseline_days = condition.get("baseline_days", 7)
        streak = condition.get("streak_days", 1)
        if len(values) < baseline_days + streak:
            return False, 0
        baseline = sum(values[-baseline_days - streak:-streak]) / baseline_days
        window = values[-streak:]
        return all(v > baseline + condition["value"] for v in window), 0

    if op == "days_since":
        # Days since the metric was last truthy, counted in daily entries.
        last_true = None
        for index in range(len(values) - 1, -1, -1):
            if values[index]:
                last_true = index
                break
        if last_true is None:
            return True, len(values)  # never logged: full history counts
        return len(values) - 1 - last_true > condition["value"], 0

    if op == "false_streak":
        # Hours without a truthy reading, using real timestamps.
        points = points_series
        if not points:
            return False, 0
        latest_time = points[-1][0]
        window = condition.get("value", 48)
        unit = condition.get("unit", "hours")
        seconds = window * 3600 if unit == "hours" else window * 86400
        last_true_time = None
        for timestamp, value in points:
            if value:
                last_true_time = timestamp
        if last_true_time is None:
            return True, 0
        return (latest_time - last_true_time).total_seconds() > seconds, 0

    if op == "false_streak_per_day":
        # Bone-loss rule: +2 points per consecutive day without a log.
        # Returns the streak length; the caller multiplies by points.
        streak = 0
        for value in reversed(values):
            if value:
                break
            streak += 1
        return streak > 0, streak

    if op == "activity_below_pct_of_target":
        window = values[-7:]
        if not window:
            return False, 0
        logged = sum(1 for value in window if value)
        return logged / len(window) < condition["value"] / 100, 0

    raise ValueError(f"Unsupported risk condition op: {op}")


def assess_history(astronaut_id, history):
    """Score one crew member's clean history across all risk domains.

    Returns {astronaut_id, assessed_at, domains}. Status mapping (prototype
    heuristic, the spec defines escalation at Orange): green = all metrics
    in range and no rules fired; yellow = a watch band or partial score
    below the trigger; orange = trigger score reached or any metric in
    alert; red = score >= 80.
    """
    series = build_series(history)
    results = {}
    for domain, model in health_data.RISK_MODELS.items():
        score = 0
        fired = []
        for rule in model["rules"]:
            metric = METRIC_ALIASES.get(rule["metric"], rule["metric"])
            matched, extra = _rule_matches(rule["condition"], series, metric)
            if matched:
                if rule["condition"]["op"] == "false_streak_per_day":
                    score += rule["points"] * extra
                else:
                    score += rule["points"]
                fired.append(rule["description"])
        score = min(score, 100)

        statuses = metric_statuses(series, domain)
        has_watch = "watch" in statuses.values()
        has_alert = "alert" in statuses.values()
        triggered = score >= model["trigger_at"]

        if score >= 80:
            status = "red"
        elif triggered or has_alert:
            status = "orange"
        elif score > 0 or has_watch:
            status = "yellow"
        else:
            status = "green"

        results[domain] = {
            "domain_status": status,
            "risk_score": score,
            "trigger_message": model["trigger_message"] if triggered else None,
            "details": {
                "metrics": statuses,
                "fired_rules": fired,
                "trigger_at": model["trigger_at"],
                "history_observations": len(history),
            },
        }
    return {"astronaut_id": astronaut_id, "assessed_at":
            datetime.now(timezone.utc).isoformat(), "domains": results}


class PocketBaseStore:
    """Thin REST wrapper over the three Step 3 collections.

    Uses the shared PocketBaseTelemetry HTTP client; authentication is a
    superuser token or email/password for the _superusers collection.
    """

    def __init__(self, client):
        self.client = client
        self._astronaut_ids = {}
        self._reading_keys = {}
        self._mission_days = {}

    @classmethod
    def from_environment(cls, env_file=None):
        settings = connection_settings(env_file)
        client = PocketBaseTelemetry(
            settings.get("POCKETBASE_URL", "http://127.0.0.1:8090"),
            settings.get("POCKETBASE_TOKEN"),
        )
        if not client.token:
            email = settings.get("POCKETBASE_EMAIL")
            password = settings.get("POCKETBASE_PASSWORD")
            if not email or not password:
                raise ValueError(
                    "Set POCKETBASE_TOKEN or POCKETBASE_EMAIL and "
                    "POCKETBASE_PASSWORD")
            client.authenticate(email, password, "_superusers")
        return cls(client)

    # -- astronauts -------------------------------------------------------

    def astronaut_id(self, crew_id):
        """Return the astronauts record id for a generator crew_id."""
        if crew_id in self._astronaut_ids:
            return self._astronaut_ids[crew_id]
        records = self.client.request(
            "GET", "/api/collections/astronauts/records",
            query={"filter": f'crew_id="{crew_id}"', "perPage": 1},
        )["items"]
        if records:
            record_id = records[0]["id"]
        else:
            record = self.client.request(
                "POST", "/api/collections/astronauts/records",
                {"crew_id": crew_id, "name": crew_id, "status": "active"},
            )
            record_id = record["id"]
        self._astronaut_ids[crew_id] = record_id
        return record_id

    # -- sensor_readings --------------------------------------------------

    def _key_set(self, astronaut_id):
        """Existing (sensor_type, captured_at epoch) pairs for dedupe."""
        if astronaut_id in self._reading_keys:
            return self._reading_keys[astronaut_id]
        keys = set()
        page = 1
        while True:
            records = self.client.request(
                "GET", "/api/collections/sensor_readings/records",
                query={
                    "filter": f'astronaut="{astronaut_id}"',
                    "sort": "captured_at,id", "perPage": 500, "page": page,
                    "skipTotal": "true",
                },
            )["items"]
            for record in records:
                if record.get("captured_at"):
                    keys.add((record["sensor_type"], _epoch(record["captured_at"])))
            if len(records) < 500:
                break
            page += 1
        self._reading_keys[astronaut_id] = keys
        return keys

    def ingest_observation(self, observation):
        """Store one validated observation as a sensor_readings record."""
        crew_id = observation["astronaut_id"]
        metric = observation["metric"]
        if metric == "mission_day":
            return None  # carried on each reading row, not a sensor_type
        sensor_type = SENSOR_TYPE_BY_METRIC.get(metric)
        if sensor_type is None:
            return None
        astronaut_id = self.astronaut_id(crew_id)
        captured_at = observation["captured_at"]
        key = (sensor_type, _epoch(captured_at))
        if key in self._key_set(astronaut_id):
            return "duplicate"
        mission_day = self._mission_days.get(
            (crew_id, _epoch(captured_at)))
        self.client.request(
            "POST", "/api/collections/sensor_readings/records",
            {
                "astronaut": astronaut_id,
                "sensor_type": sensor_type,
                "value": _serialize_value(observation["value"]),
                "unit": observation["unit"],
                "captured_at": _pb_datetime(captured_at),
                "mission_day": mission_day,
            },
        )
        self._key_set(astronaut_id).add(key)
        return "accepted"

    def parse_packets(self, packets, *, assume_utc=False, reference_time=None):
        """Run the Step 1->2 parser and store accepted observations.

        mission_day observations arrive last within each packet, so the
        batch is validated first and the day map is built before any
        sensor_readings row is written.

        Returns counts of accepted, quarantined, and duplicate outcomes.
        """
        accepted = []
        counts = {"accepted": 0, "quarantined": 0, "duplicates": 0}
        for raw in sensor_observations(packets, assume_utc=assume_utc):
            result = validate_observation(raw, reference_time=reference_time)
            observation = result["observation"]
            if observation is None:
                counts["quarantined"] += 1
            else:
                accepted.append(observation)

        self._mission_days = {
            (obs["astronaut_id"], _epoch(obs["captured_at"])): obs["value"]
            for obs in accepted if obs["metric"] == "mission_day"
        }
        for observation in accepted:
            outcome = self.ingest_observation(observation)
            if outcome == "duplicate":
                counts["duplicates"] += 1
            elif outcome:
                counts["accepted"] += 1
        self._mission_days = {}
        return counts

    # -- history + assessments --------------------------------------------

    def get_history(self, crew_id, limit=10000):
        """Read sensor_readings back as assessment-shaped observations."""
        astronaut_id = self.astronaut_id(crew_id)
        history = []
        page = 1
        while len(history) < limit:
            records = self.client.request(
                "GET", "/api/collections/sensor_readings/records",
                query={
                    "filter": f'astronaut="{astronaut_id}"',
                    "sort": "-captured_at,-id", "perPage": 500, "page": page,
                    "skipTotal": "true",
                },
            )["items"]
            for record in records:
                history.append({
                    "astronaut_id": crew_id,
                    "metric": record["sensor_type"],
                    "value": _deserialize_value(
                        record["sensor_type"], record["value"]),
                    "unit": record.get("unit") or "",
                    "captured_at": record["captured_at"],
                })
            if len(records) < 500 or len(history) >= limit:
                break
            page += 1
        return history[:limit]

    def save_assessment(self, crew_id, assessment):
        """Post one domain_assessments record per domain."""
        astronaut_id = self.astronaut_id(crew_id)
        for domain, result in assessment["domains"].items():
            self.client.request(
                "POST", "/api/collections/domain_assessments/records",
                {
                    "astronaut": astronaut_id,
                    "domain": domain,
                    "domain_status": result["domain_status"],
                    "risk_score": result["risk_score"],
                    "details": result["details"],
                },
            )


def ingest_packets(store, packets, *, assume_utc=False, reference_time=None):
    """Parse a batch of generator packets and store accepted readings."""
    return store.parse_packets(
        packets, assume_utc=assume_utc, reference_time=reference_time)


def assess_crew(store, crew_id):
    """Score one crew member from stored readings and post the result."""
    history = store.get_history(crew_id)
    assessment = assess_history(crew_id, history)
    store.save_assessment(crew_id, assessment)
    return {
        domain: {"domain_status": r["domain_status"],
                 "risk_score": r["risk_score"]}
        for domain, r in assessment["domains"].items()
    }


def run_story(store):
    """Bootstrap: ingest the full synthetic mission, then assess each crew."""
    packets, reference_time = simulated_mission()
    counts = ingest_packets(store, packets, assume_utc=True,
                            reference_time=reference_time)
    crew_ids = sorted({packet["crew_id"] for packet in packets})
    return {
        "ingestion": counts,
        "assessments": {crew: assess_crew(store, crew) for crew in crew_ids},
    }


def run_ticks(store, mode, ticks, interval):
    """Live mode: pull bounded ticks from the generator and process each."""
    outputs = []
    for packets, clock, assume_utc in sensor_batches(mode, ticks):
        counts = ingest_packets(store, packets, assume_utc=assume_utc,
                                reference_time=clock)
        crew_ids = sorted({packet["crew_id"] for packet in packets})
        outputs.append({
            "ingestion": counts,
            "assessments": {crew: assess_crew(store, crew)
                            for crew in crew_ids},
        })
        if interval:
            time.sleep(interval)
    return outputs


def main():
    parser = argparse.ArgumentParser(
        description="Assess crew health from the synthetic sensor pipeline")
    parser.add_argument("--env-file",
                        default=str(_REPO_ROOT / "backend" / ".env"),
                        help="PocketBase settings file")
    parser.add_argument("--mode", choices=("story", "noise"), default="story",
                        help="story runs the fixed 7-day mission once; "
                             "noise streams generator ticks")
    parser.add_argument("--ticks", type=int,
                        help="Noise mode tick count (default: continuous)")
    parser.add_argument("--interval", type=float, default=3,
                        help="Seconds between noise ticks")
    args = parser.parse_args()

    store = PocketBaseStore.from_environment(args.env_file)

    if args.mode == "story":
        print(json.dumps(run_story(store), indent=2, allow_nan=False))
    else:
        try:
            for result in run_ticks(store, args.mode, args.ticks,
                                    args.interval):
                print(json.dumps(result, allow_nan=False), flush=True)
        except KeyboardInterrupt:
            pass  # Already committed readings and assessments persist.


if __name__ == "__main__":
    main()
