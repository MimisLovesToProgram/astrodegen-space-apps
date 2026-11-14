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


if __name__ == "__main__":
    unittest.main()
