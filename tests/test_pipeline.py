"""Verify the real simulator -> Step 2 -> assessment interface."""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from biosensors import Crew, reading_from
from ingest_validate import get_validated_observations, process_sensor_packets
from ingest_validate.pipeline import simulated_mission


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "telemetry.sqlite"
        self.packet = reading_from("a", Crew["a"][0], 1)
        self.now = datetime(2026, 11, 22, tzinfo=timezone.utc)

    def run_pipeline(self, packets, **kwargs):
        return process_sensor_packets(packets, self.db, reference_time=self.now, **kwargs)

    def test_complete_mission_reaches_step3(self):
        packets, clock = simulated_mission()
        calls = []
        def assess(crew_id, history):
            # Record what Step 3 receives without pretending to implement risk
            # calculations. The assertions below verify the integration boundary.
            calls.append((crew_id, history))
            return {"test_received": len(history)}
        result = process_sensor_packets(packets, self.db, reference_time=clock, assume_utc=True, assess=assess)
        self.assertEqual(len(result["ingestion"]["accepted"]), 252)
        self.assertEqual(len(result["ingestion"]["quarantined"]), 0)
        self.assertEqual(result["assessment_status"], "completed")
        self.assertEqual([crew for crew, _ in calls], ["a", "b", "c"])
        self.assertTrue(all(len(history) == 84 for _, history in calls))
        history = result["step3_history"]["a"]
        self.assertTrue(all(item["context"]["simulated"] for item in history))
        self.assertIn("symptoms", {item["metric"] for item in history})
        self.assertTrue(all(item["captured_at"].endswith("Z") for item in history))
        second = process_sensor_packets(packets, self.db, reference_time=clock, assume_utc=True, assess=assess)
        self.assertEqual(len(second["ingestion"]["duplicates"]), 252)
        self.assertEqual(len(calls), 3)

    def test_naive_timestamps_require_explicit_assumption(self):
        result = self.run_pipeline([self.packet])
        self.assertEqual(len(result["ingestion"]["quarantined"]), 12)
        self.assertEqual(result["step3_history"], {})

    def test_bad_metric_does_not_reach_assessor(self):
        self.packet["spo2"] = 140
        calls = []
        result = self.run_pipeline([self.packet], assume_utc=True, assess=lambda crew, history: calls.append(history))
        self.assertEqual(len(result["ingestion"]["accepted"]), 11)
        self.assertEqual(len(result["ingestion"]["quarantined"]), 1)
        self.assertNotIn("spo2", {item["metric"] for item in calls[0]})
        with sqlite3.connect(self.db) as connection:
            payload = connection.execute("SELECT payload FROM sensor_packets LIMIT 1").fetchone()[0]
        self.assertEqual(json.loads(payload), self.packet)

    def test_missing_and_invalid_fields_are_quarantined(self):
        del self.packet["hr"]
        self.packet["symptoms"] = [4]
        result = self.run_pipeline([self.packet, "malformed JSON"], assume_utc=True)
        self.assertEqual(len(result["ingestion"]["accepted"]), 10)
        self.assertEqual(len(result["ingestion"]["quarantined"]), 3)

    def test_failed_assessor_keeps_history_for_retry(self):
        def fail(crew, history):
            raise RuntimeError("Assessment unavailable")
        with self.assertRaises(RuntimeError):
            self.run_pipeline([self.packet], assume_utc=True, assess=fail)
        self.assertEqual(len(get_validated_observations(self.db, "a")), 12)

    def test_aware_sensor_time_needs_no_assumption(self):
        self.packet["timestamp"] += "+00:00"
        result = self.run_pipeline([self.packet])
        self.assertEqual(len(result["ingestion"]["accepted"]), 12)
        self.assertEqual(result["assessment_status"], "not_configured")

    def test_future_sensor_time_still_rejected(self):
        self.packet["timestamp"] = "2099-01-01T00:00:00Z"
        result = self.run_pipeline([self.packet], assume_utc=True)
        self.assertEqual(len(result["ingestion"]["quarantined"]), 12)


if __name__ == "__main__":
    unittest.main()
