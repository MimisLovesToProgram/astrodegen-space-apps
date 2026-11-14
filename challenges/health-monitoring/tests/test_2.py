"""Run with PYTHONPATH=challenges/health-monitoring/src python3 -m unittest discover -s challenges/health-monitoring/tests -v."""

import unittest
from datetime import datetime, timezone

from ingest_validate import validate_observation


NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)


def measurement(**changes):
    raw = {
        "astronaut_id": "crew_01", "metric": "hr_resting", "value": 135,
        "unit": "bpm", "captured_at": "2026-11-14T11:30:00Z",
        "source": "synthetic_wearable_01", "context": {"simulated": True},
    }
    raw.update(changes)
    return raw


class ValidationTests(unittest.TestCase):
    def test_high_heart_rate_is_valid_data(self):
        result = validate_observation(measurement(), NOW)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["observation"]["value"], 135)

    def test_conversions(self):
        for metric, value, unit, expected, target in (
            ("temp_c", 100.6, "F", 38.1111111111, "C"),
            ("sleep_h", 420, "min", 7, "h"),
        ):
            with self.subTest(metric=metric):
                observation = validate_observation(measurement(metric=metric, value=value, unit=unit), NOW)["observation"]
                self.assertAlmostEqual(observation["value"], expected)
                self.assertEqual(observation["unit"], target)
                self.assertTrue(observation["quality_flags"])

    def test_invalid_payloads(self):
        for raw in (
            None, {}, measurement(metric="unknown"), measurement(source=" "),
            measurement(metric="spo2", unit="%", value=140),
            measurement(value=True), measurement(value="85"),
            measurement(value=float("nan")), measurement(value=float("inf")),
            measurement(value=10 ** 400), measurement(unit="ms"),
            measurement(context=[]), measurement(context={"bad": object()}),
            measurement(metric="mood", unit="score_1_5", value=2.5),
            measurement(captured_at="2026-11-14T11:30:00"),
            measurement(captured_at="not a date"),
            measurement(captured_at="2026-11-14T12:06:00Z"),
        ):
            with self.subTest(raw=raw):
                result = validate_observation(raw, NOW)
                self.assertEqual(result["status"], "quarantined")
                self.assertTrue(result["errors"])

    def test_boolean_metrics(self):
        raw = measurement(metric="exercise_logged", value=True, unit="bool")
        self.assertEqual(validate_observation(raw, NOW)["status"], "accepted")
        raw["value"] = 1
        self.assertEqual(validate_observation(raw, NOW)["status"], "quarantined")

    def test_timezone_normalization(self):
        result = validate_observation(measurement(captured_at="2026-11-14T13:30:00+02:00"), NOW)
        self.assertEqual(result["observation"]["captured_at"], "2026-11-14T11:30:00.000000Z")

    def test_context_is_detached(self):
        raw = measurement()
        observation = validate_observation(raw, NOW)["observation"]
        raw["context"]["simulated"] = False
        self.assertTrue(observation["context"]["simulated"])


if __name__ == "__main__":
    unittest.main()
