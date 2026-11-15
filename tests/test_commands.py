"""Check the user-facing commands with isolated local storage."""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from astrocrates import sensor_batches


class CommandTests(unittest.TestCase):
    def test_capture_then_process_full_mission(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "mission.sqlite")
            base = [sys.executable, "-m", "astrocrates", "--backend", "sqlite", "--db", db]
            def run(*arguments):
                # Exercise the same executable commands used in the README;
                # parse their output instead of calling internal helpers only.
                return [json.loads(line) for line in subprocess.check_output(
                    [*base, *arguments], env=env, cwd=root, text=True,
                ).splitlines() if line.strip()]
            output = run("capture", "--interval", "0")
            self.assertEqual(sum(item["captured_packets"] for item in output), 21)
            with sqlite3.connect(db) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM sensor_packets WHERE status='pending'").fetchone()[0], 21)
                self.assertEqual(connection.execute("SELECT count(*) FROM validated_observations").fetchone()[0], 0)
            first = run("process", "--limit", "2")[0]
            self.assertEqual(first["processed_packets"], 2)
            self.assertEqual(first["counts"]["accepted"], 24)
            self.assertEqual(run("process")[0]["counts"]["accepted"], 228)
            # history is pretty-printed JSON, so read the entire response.
            history = json.loads(subprocess.check_output([*base, "history", "a"], env=env, cwd=root))
            self.assertEqual(len(history), 84)
            replay = run("capture", "--interval", "0", "--process")
            self.assertEqual(sum(item["counts"]["duplicates"] for item in replay), 252)
            quality = json.loads(subprocess.check_output([
                *base, "quality", "a", "--max-age-seconds", "86400", "--reference-time", "2026-11-22T00:00:00Z",
            ], env=env, cwd=root))
            self.assertEqual(quality["missing_metrics"], [])
            self.assertEqual(quality["stale_metrics"], [])
            self.assertEqual(quality["fresh_metric_fraction"], 1)
            self.assertEqual(quality["audit"]["sources"]["synthetic_biosensors"]["duplicate"], 252)

    def test_noise_packets_use_aware_utc(self):
        packets, clock, assumed = next(sensor_batches("noise", ticks=1))
        self.assertIsNone(clock)
        self.assertFalse(assumed)
        for packet in packets:
            parsed = datetime.fromisoformat(packet["timestamp"])
            self.assertEqual(parsed.utcoffset().total_seconds(), 0)

    def test_monitor_alerts_recover_and_watch_is_bounded(self):
        from datetime import timezone
        from ingest_validate import ingest_batch
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "alerts.sqlite")
            base = [sys.executable, "-m", "astrocrates", "--backend", "sqlite", "--db", db]
            def run(*arguments):
                return json.loads(subprocess.check_output([*base, *arguments], env=env, cwd=root))
            options = ["monitor", "a", "--metrics", "spo2", "--source", "sensor", "--max-age-seconds", "60", "--policy", "test"]
            first = run(*options, "--reference-time", "2026-11-22T12:00:00Z")
            self.assertEqual(first["alert_changes"]["opened"], 1)
            self.assertEqual(run(*options, "--reference-time", "2026-11-22T12:00:00Z")["alert_changes"]["opened"], 0)
            ingest_batch([{"astronaut_id": "a", "metric": "spo2", "value": 97, "unit": "%",
                           "source": "sensor", "captured_at": "2026-11-22T12:01:00Z"}], db,
                         reference_time=datetime(2026, 11, 22, 12, 1, tzinfo=timezone.utc))
            recovered = run(*options, "--reference-time", "2026-11-22T12:01:00Z")
            self.assertEqual(recovered["alert_changes"]["resolved"], 1)
            self.assertEqual(len(run("alerts", "--astronaut-id", "a", "--status", "resolved")), 1)
            # We bound watch mode in tests so it cannot leave a background
            # process running after the assertion completes.
            watched = run("monitor", "b", "--metrics", "spo2", "--max-age-seconds", "60",
                          "--watch", "--checks", "2", "--interval", "0.01")
            self.assertEqual(watched["alert_changes"]["opened"], 1)
            self.assertEqual(len(run("alerts", "--astronaut-id", "b")), 1)

    def test_real_checkin_does_not_use_future_simulator_clock(self):
        from datetime import timezone
        from unittest.mock import Mock
        from astrocrates import report_processed
        from assessment_fixtures import observation, sample_policy
        store = Mock()
        store.get_history.return_value = [observation(captured_at="2099-01-01T12:00:00Z")]
        store.enqueue_assessment.return_value = {"id": "job"}
        accepted = observation(metric="mood", context={"simulated": False})
        before = datetime.now(timezone.utc)
        report_processed(store, {"packet_ids": ["packet"], "ingestion": {
            "accepted": [accepted], "duplicates": [], "quarantined": [], "conflicts": []}}, sample_policy())
        clock = store.enqueue_assessment.call_args.kwargs["as_of"]
        self.assertGreaterEqual(clock, before)
        self.assertLessEqual(clock, datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
