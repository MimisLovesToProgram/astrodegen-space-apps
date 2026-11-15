"""Check alert deduplication, recovery, policy isolation, and transaction safety."""

import copy
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from ingest_validate.alerts import alert_snapshot, list_quality_alerts, save_quality_alerts
from ingest_validate.quality import quality_report


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "telemetry.sqlite"

    def snapshot(self, minute=2, present=False, policy="test"):
        history = [{"astronaut_id": "a", "metric": "spo2", "source": "sensor",
                    "captured_at": f"2026-11-22T12:{minute:02d}:00Z", "value": 97}] if present else []
        report = quality_report(history, "a", max_age_seconds=60, expected_metrics=["spo2"],
                                reference_time=datetime(2026, 11, 22, 12, minute, tzinfo=timezone.utc))
        return alert_snapshot(report, policy)

    def test_repeated_checks_resolve_and_reopen_one_alert(self):
        first = self.snapshot()
        self.assertEqual(save_quality_alerts(first, self.db)["opened"], 1)
        self.assertEqual(save_quality_alerts(first, self.db)["opened"], 0)
        self.assertEqual(save_quality_alerts(self.snapshot(3, present=True), self.db)["resolved"], 1)
        self.assertEqual(list_quality_alerts(self.db), [])
        result = save_quality_alerts(self.snapshot(4), self.db)
        self.assertEqual(result["reopened"], 1)
        rows = list_quality_alerts(self.db, status="all")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["occurrences"], 2)

    def test_old_report_cannot_undo_recovery(self):
        old = self.snapshot()
        save_quality_alerts(old, self.db)
        save_quality_alerts(self.snapshot(3, present=True), self.db)
        self.assertTrue(save_quality_alerts(old, self.db)["ignored_older_report"])
        self.assertEqual(list_quality_alerts(self.db), [])

    def test_policies_are_isolated(self):
        save_quality_alerts(self.snapshot(policy="live"), self.db)
        save_quality_alerts(self.snapshot(3, present=True, policy="daily"), self.db)
        self.assertEqual(len(list_quality_alerts(self.db, policy_name="live")), 1)

    def test_concurrent_monitors_create_one_record(self):
        snapshot = self.snapshot()
        save_quality_alerts(self.snapshot(present=True), self.db)
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda _: save_quality_alerts(snapshot, self.db), range(3)))
        self.assertEqual(sum(result["opened"] for result in results), 1)
        self.assertEqual(len(list_quality_alerts(self.db)), 1)

    def test_failed_snapshot_is_atomic(self):
        save_quality_alerts(self.snapshot(present=True), self.db)
        with sqlite3.connect(self.db) as connection:
            connection.execute("""CREATE TRIGGER fail_alert BEFORE INSERT ON quality_alerts
                BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            save_quality_alerts(self.snapshot(3), self.db)
        self.assertEqual(list_quality_alerts(self.db, status="all"), [])
        with sqlite3.connect(self.db) as connection:
            self.assertTrue(connection.execute("SELECT checked_at FROM quality_checks").fetchone()[0].startswith("2026-11-22T12:02:"))

    def test_invalid_alert_identity_is_rejected(self):
        snapshot = copy.deepcopy(self.snapshot())
        snapshot["alerts"][0]["alert_key"] = "wrong"
        with self.assertRaises(ValueError):
            save_quality_alerts(snapshot, self.db)

    def test_version_one_database_keeps_existing_audit_records(self):
        save_quality_alerts(self.snapshot(), self.db)
        with sqlite3.connect(self.db) as connection:
            connection.execute("DROP TABLE quality_alerts")
            connection.execute("DROP TABLE quality_checks")
            connection.execute("PRAGMA user_version=1")
            connection.execute("""INSERT INTO raw_measurements
                (received_at,payload,payload_encoding,status,errors_json)
                VALUES ('old','{}','json','quarantined','[]')""")
        save_quality_alerts(self.snapshot(), self.db)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM raw_measurements").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
