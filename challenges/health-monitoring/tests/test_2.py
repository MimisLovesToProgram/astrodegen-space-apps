"""Run with PYTHONPATH=challenges/health-monitoring/src python3 -m unittest discover -s challenges/health-monitoring/tests -v."""

import unittest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from ingest_validate import validate_observation, ingest_batch, get_validated_observations


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


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "nested" / "telemetry.sqlite"

    def ingest(self, records):
        return ingest_batch(records, self.db, reference_time=NOW)

    def test_demo_and_persistent_retransmission(self):
        from ingest_validate.cli import demo_measurements
        records = demo_measurements()
        first = self.ingest(records)
        self.assertEqual({k: len(v) for k, v in first.items()}, {
            "accepted": 4, "quarantined": 1, "duplicates": 0, "conflicts": 0,
        })
        second = self.ingest(records)
        self.assertEqual(len(second["accepted"]), 0)
        self.assertEqual(len(second["duplicates"]), 4)
        self.assertEqual(len(second["quarantined"]), 1)
        self.assertEqual(len(get_validated_observations(self.db, "crew_01")), 4)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM raw_measurements").fetchone()[0], 10)

    def test_conflict_preserves_original(self):
        result = self.ingest([measurement(), measurement(value=80)])
        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertEqual(get_validated_observations(self.db, "crew_01")[0]["value"], 135)

    def test_normalized_duplicates(self):
        result = self.ingest([
            measurement(captured_at="2026-11-14T13:30:00+02:00"),
            measurement(value=135.0),
        ])
        self.assertEqual(len(result["duplicates"]), 1)
        result = self.ingest([
            measurement(metric="sleep_h", value=420, unit="min"),
            measurement(metric="sleep_h", value=7, unit="h"),
        ])
        self.assertEqual(len(result["duplicates"]), 1)

    def test_context_change_is_conflict(self):
        result = self.ingest([measurement(), measurement(context={"simulated": False})])
        self.assertEqual(len(result["conflicts"]), 1)

    def test_history_order_limit_and_crew_isolation(self):
        self.ingest([
            measurement(captured_at="2026-11-14T10:00:00Z"),
            measurement(value=80), measurement(astronaut_id="crew_02"),
        ])
        history = get_validated_observations(self.db, "crew_01", limit=1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["value"], 80)
        self.assertEqual(get_validated_observations(self.db, "unknown"), [])
        for limit in (True, 0, 10001, "1"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                get_validated_observations(self.db, "crew_01", limit)

    def test_invalid_raw_deliveries_are_audited(self):
        result = self.ingest([None, measurement(value=float("nan")), measurement(context={"x": object()})])
        self.assertEqual(len(result["quarantined"]), 3)
        self.assertEqual(get_validated_observations(self.db, "crew_01"), [])
        with sqlite3.connect(self.db) as connection:
            rows = connection.execute("SELECT payload, payload_encoding, status FROM raw_measurements ORDER BY id").fetchall()
        self.assertEqual(rows[0], ("null", "json", "quarantined"))
        self.assertEqual(rows[1][1:], ("python_repr", "quarantined"))

    def test_batch_failure_rolls_back(self):
        def failing_batch():
            yield measurement()
            raise RuntimeError("Sensor stream disconnected")
        with self.assertRaises(RuntimeError):
            self.ingest(failing_batch())
        self.assertEqual(get_validated_observations(self.db, "crew_01"), [])
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM raw_measurements").fetchone()[0], 0)

    def test_new_timestamp_is_new_measurement(self):
        result = self.ingest([measurement(), measurement(captured_at="2026-11-14T11:31:00Z")])
        self.assertEqual(len(result["accepted"]), 2)


if __name__ == "__main__":
    unittest.main()
