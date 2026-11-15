"""Real API tests: set POCKETBASE_TEST_BINARY to an installed executable."""

import os
import socket
import json
import sys
import subprocess
import tempfile
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

from biosensors import Crew, reading_from
from ingest_validate.pocketbase import PocketBaseError, PocketBaseTelemetry
from ingest_validate.alerts import alert_snapshot
from ingest_validate.quality import quality_report


@unittest.skipUnless(os.environ.get("POCKETBASE_TEST_BINARY"), "Set POCKETBASE_TEST_BINARY to run real API tests")
class PocketBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Launch a real server with temporary storage and generated credentials.
        # No account or collection on the configured local demo is modified.
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.log = open(Path(cls.directory.name) / "server.log", "w+")
        cls.addClassCleanup(cls.log.close)
        root = Path(__file__).resolve().parents[1]
        options = ["--dir", str(Path(cls.directory.name) / "pb_data"),
                   "--migrationsDir", str(root / "backend/pb_migrations")]
        password = uuid.uuid4().hex
        binary = os.environ["POCKETBASE_TEST_BINARY"]
        subprocess.run([binary, "superuser", "create", "test@example.com", password, *options],
                       check=True, stdout=cls.log, stderr=cls.log)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.url = f"http://127.0.0.1:{port}"
        process = subprocess.Popen([binary, "serve", "--http", f"127.0.0.1:{port}", *options,
                                    "--hooksDir", str(root / "backend/pb_hooks")],
                                   stdout=cls.log, stderr=cls.log)
        def stop():
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        cls.addClassCleanup(stop)
        cls.admin = PocketBaseTelemetry(cls.url)
        for _ in range(100):
            try:
                cls.admin.request("GET", "/api/health")
                break
            except (URLError, TimeoutError):
                if process.poll() is not None:
                    cls.log.seek(0)
                    raise RuntimeError(cls.log.read())
                time.sleep(0.05)
        cls.admin.authenticate("test@example.com", password, "_superusers")
        cls.clients = {}
        for role in ("ingest", "worker", "reader"):
            email = f"{role}@example.com"
            cls.admin.request("POST", "/api/collections/telemetry_services/records", {
                "email": email, "password": password, "passwordConfirm": password, "role": role,
            })
            client = PocketBaseTelemetry(cls.url)
            client.authenticate(email, password)
            cls.clients[role] = client

    def setUp(self):
        for collection in ("quality_alerts", "quality_checks", "validated_observations", "validation_results", "sensor_packets"):
            path = f"/api/collections/{collection}/records"
            while True:
                rows = self.admin.request("GET", path, query={"perPage": 500})["items"]
                if not rows:
                    break
                for row in rows:
                    self.admin.request("DELETE", path + "/" + row["id"])
        self.packet = reading_from("a", Crew["a"][0], 1)
        self.clock = datetime(2026, 11, 22, tzinfo=timezone.utc)
        self.ingest = self.clients["ingest"]
        self.worker = self.clients["worker"]

    def capture(self, packet=None, **kwargs):
        return self.ingest.capture(self.packet if packet is None else packet,
                                   assume_utc=True, reference_time=self.clock, **kwargs)

    def test_capture_is_durable_and_bad_values_stay_out_of_history(self):
        self.packet["spo2"] = 140
        captured = self.capture()
        self.assertEqual(self.worker.get_history("a"), [])
        result = self.worker.process_pending()
        self.assertEqual(result["packet_ids"], [captured["id"]])
        self.assertEqual(len(result["ingestion"]["accepted"]), 11)
        self.assertEqual(len(result["ingestion"]["quarantined"]), 1)
        self.assertEqual(len(self.clients["reader"].get_history("a")), 11)
        self.assertEqual(self.worker.process_pending()["packet_ids"], [])

    def test_capture_retry_and_retransmission(self):
        first = self.capture(delivery_key="retry-key")
        self.assertEqual(self.capture(delivery_key="retry-key")["id"], first["id"])
        self.worker.process_pending()
        self.capture()
        self.assertEqual(len(self.worker.process_pending()["ingestion"]["duplicates"]), 12)
        self.packet["hr"] = 80
        with self.assertRaises(PocketBaseError):
            self.capture(delivery_key="retry-key")
        self.capture()
        result = self.worker.process_pending()
        self.assertEqual(len(result["ingestion"]["conflicts"]), 1)
        self.assertEqual(len(self.worker.get_history("a")), 12)

    def test_commit_failure_rolls_back_entire_packet(self):
        # Reject a later normalized result after an earlier result was written;
        # no partial clean history may survive the failed server transaction.
        captured = self.capture()
        record = self.worker.request("GET", "/api/collections/sensor_packets/records/" + captured["id"])
        results = self.worker.validation_results(record)
        results[1]["observation"] = None
        with self.assertRaises(PocketBaseError):
            self.worker.request("POST", "/api/astrocrates/commit", {"packet_id": captured["id"], "results": results})
        self.assertEqual(self.worker.get_history("a"), [])
        record = self.worker.request("GET", "/api/collections/sensor_packets/records/" + captured["id"])
        self.assertEqual(record["status"], "pending")
        self.assertEqual(len(self.worker.process_pending()["ingestion"]["accepted"]), 12)

    def test_workers_commit_once(self):
        self.capture()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.worker.process_pending(), range(2)))
        self.assertEqual(sum(len(result["ingestion"]["accepted"]) for result in results), 12)

    def test_roles_restrict_capture_processing_and_clean_writes(self):
        reader = self.clients["reader"]
        with self.assertRaises(PocketBaseError) as error:
            reader.capture(self.packet)
        self.assertEqual(error.exception.status, 403)
        with self.assertRaises(PocketBaseError):
            self.ingest.request("POST", "/api/astrocrates/commit", {"packet_id": "x", "results": []})
        with self.assertRaises(PocketBaseError):
            reader.request("POST", "/api/collections/validated_observations/records", {})
        with self.assertRaises(PocketBaseError) as error:
            PocketBaseTelemetry(self.url).capture(self.packet)
        self.assertIn(error.exception.status, (401, 403))

    def test_commands_capture_and_process_the_full_mission(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"),
                   POCKETBASE_URL=self.url, POCKETBASE_TOKEN=self.worker.token)
        command = [sys.executable, "-m", "astrocrates"]
        captured = subprocess.check_output([*command, "capture", "--interval", "0"], env=env, cwd=root, text=True)
        self.assertEqual(sum(json.loads(line)["captured_packets"] for line in captured.splitlines()), 21)
        output = json.loads(subprocess.check_output([*command, "process"], env=env, cwd=root))
        self.assertEqual(output["counts"]["accepted"], 252)
        self.assertEqual(len(self.clients["reader"].get_history("a")), 84)

    def test_quality_summary_counts_outcomes_and_restricts_access(self):
        # One bad field must affect the source acceptance rate without
        # preventing the other eleven metrics from reaching clean history.
        self.packet["spo2"] = 140
        self.capture()
        self.worker.process_pending()
        summary = self.worker.get_audit_summary()
        self.assertEqual(summary["packets"], {"pending": 0, "processed": 1})
        counts = {row["status"]: row["total"] for row in summary["results"]}
        self.assertEqual(counts, {"accepted": 11, "quarantined": 1})
        with self.assertRaises(PocketBaseError) as error:
            self.clients["reader"].get_audit_summary()
        self.assertEqual(error.exception.status, 403)

    def monitoring_snapshot(self, minute=2, present=False):
        history = [{"astronaut_id": "a", "metric": "spo2", "source": "sensor",
                    "captured_at": f"2026-11-22T12:{minute:02d}:00Z"}] if present else []
        return alert_snapshot(quality_report(
            history, "a", max_age_seconds=60, expected_metrics=["spo2"],
            reference_time=datetime(2026, 11, 22, 12, minute, tzinfo=timezone.utc)), "test")

    def test_alert_lifecycle_and_permissions(self):
        snapshot = self.monitoring_snapshot()
        self.assertEqual(self.worker.save_quality_alerts(snapshot)["opened"], 1)
        self.assertEqual(self.worker.save_quality_alerts(snapshot)["opened"], 0)
        self.assertEqual(len(self.clients["reader"].list_quality_alerts()), 1)
        with self.assertRaises(PocketBaseError) as error:
            self.clients["ingest"].save_quality_alerts(snapshot)
        self.assertEqual(error.exception.status, 403)
        self.assertEqual(self.worker.save_quality_alerts(self.monitoring_snapshot(3, True))["resolved"], 1)
        self.assertTrue(self.worker.save_quality_alerts(snapshot)["ignored_older_report"])
        self.assertEqual(self.worker.list_quality_alerts(), [])
        self.assertEqual(self.worker.save_quality_alerts(self.monitoring_snapshot(4))["reopened"], 1)
        self.assertEqual(self.worker.list_quality_alerts()[0]["occurrences"], 2)

    def test_concurrent_monitors_open_one_alert(self):
        snapshot = self.monitoring_snapshot()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.worker.save_quality_alerts(snapshot), range(2)))
        self.assertEqual(sum(result["opened"] for result in results), 1)
        self.assertEqual(len(self.worker.list_quality_alerts()), 1)

    def test_alert_failure_rolls_back_the_complete_snapshot(self):
        snapshot = alert_snapshot(quality_report(
            [], "a", max_age_seconds=60, expected_metrics=["spo2", "mood"],
            reference_time=datetime(2026, 11, 22, 12, 2, tzinfo=timezone.utc)), "test")
        # We force the second insert to violate a collection constraint, after
        # the first insert has run, to verify server-side transaction rollback.
        snapshot["alerts"][1]["metric"] = "x" * 101
        with self.assertRaises(PocketBaseError):
            self.worker.request("POST", "/api/astrocrates/quality-alerts", snapshot)
        self.assertEqual(self.worker.list_quality_alerts(status="all"), [])
        checks = self.worker.request("GET", "/api/collections/quality_checks/records")
        self.assertEqual(checks["totalItems"], 0)


if __name__ == "__main__":
    unittest.main()
