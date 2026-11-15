"""Real API tests: set POCKETBASE_TEST_BINARY to an installed executable."""

import os
import copy
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
from assessment import assess_history
from assessment.jobs import run_jobs
from assessment_fixtures import observation, sample_policy


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
                   "--migrationsDir", str(root / "backend/pb_migrations"), "--automigrate=false"]
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
        for collection in ("escalation_events", "domain_assessments", "assessment_runs", "assessment_jobs", "astronauts",
                           "quality_alerts", "quality_checks", "validated_observations", "validation_results", "sensor_packets"):
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

    def test_assessment_jobs_and_escalation_transitions(self):
        policy = sample_policy()
        for domain in policy["domains"].values():
            domain["rules"].append({**domain["rules"][0], "id": "higher", "threshold": 90, "points": 20, "level": 3})
        history = []
        for day, value, expected_events in ((4, 60, 0), (5, 85, 4), (6, 85, 0), (7, 95, 4)):
            history.append(observation(value, day=day))
            clock = datetime(2026, 11, day, 12, tzinfo=timezone.utc)
            job = self.worker.enqueue_assessment(history, "a", policy, as_of=clock)
            duplicate = self.worker.enqueue_assessment(list(reversed(history)), "a", policy, as_of=clock)
            self.assertEqual(job["id"], duplicate["id"])
            result = run_jobs(self.worker, job_id=job["id"])
            self.assertEqual(result["failed"], [])
            self.assertEqual(len(result["completed"]), 1)
            self.assertEqual(result["escalation_events"], expected_events)
        runs = self.clients["reader"].get_assessments("a")
        self.assertEqual(len(runs), 4)
        self.assertEqual(runs[0]["overall_level"], 3)
        self.assertEqual(len(self.clients["reader"].list_escalations(astronaut_id="a")), 8)

    def test_assessment_retry_and_expired_lease(self):
        clock = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
        job = self.worker.enqueue_assessment([observation(85)], "a", sample_policy(), as_of=clock)
        first = self.worker.claim_assessment_job(job_id=job["id"])
        self.worker.fail_assessment_job(job["id"], first["claim_token"], "Synthetic failure")
        self.assertIsNone(self.worker.claim_assessment_job(job_id=job["id"]))
        self.worker.retry_assessment_job(job["id"])
        second = self.worker.claim_assessment_job(job_id=job["id"])
        self.admin.request("PATCH", "/api/collections/assessment_jobs/records/" + job["id"],
                           {"lease_until": "2000-01-01T00:00:00.000Z"})
        third = self.worker.claim_assessment_job(job_id=job["id"])
        self.assertNotEqual(second["claim_token"], third["claim_token"])
        result = assess_history(third["observations"], "a", third["policy"], as_of=clock)
        with self.assertRaises(PocketBaseError) as error:
            self.worker.complete_assessment_job(job["id"], second["claim_token"], result)
        self.assertEqual(error.exception.status, 409)
        self.worker.complete_assessment_job(job["id"], third["claim_token"], result)
        self.assertEqual(len(self.worker.get_assessments("a")), 1)

    def test_assessment_result_commit_is_atomic(self):
        clock = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
        job = self.worker.enqueue_assessment([observation(85)], "a", sample_policy(), as_of=clock)
        claim = self.worker.claim_assessment_job(job_id=job["id"])
        result = assess_history(claim["observations"], "a", claim["policy"], as_of=clock)
        schema = self.admin.request("GET", "/api/collections/domain_assessments")
        fields = copy.deepcopy(schema["fields"])
        next(field for field in fields if field["name"] == "risk_score")["max"] = 50
        # We use the supported schema API in the isolated server to force a
        # later domain insert to fail after the result transaction has begun.
        self.admin.request("PATCH", "/api/collections/domain_assessments", {"fields": fields})
        try:
            with self.assertRaises(PocketBaseError):
                self.worker.complete_assessment_job(job["id"], claim["claim_token"], result)
            self.assertEqual(self.worker.get_assessments("a"), [])
            self.assertEqual(self.worker.list_escalations(), [])
        finally:
            self.admin.request("PATCH", "/api/collections/domain_assessments", {"fields": schema["fields"]})

    def test_unknown_assessment_does_not_create_green_domain_rows(self):
        job = self.worker.enqueue_assessment([], "a", sample_policy(),
                                              as_of=datetime(2026, 11, 5, 12, tzinfo=timezone.utc))
        result = run_jobs(self.worker, job_id=job["id"])
        self.assertEqual(result["failed"], [])
        self.assertIsNone(self.worker.get_assessments("a")[0]["overall_level"])
        rows = self.admin.request("GET", "/api/collections/domain_assessments/records")
        self.assertEqual(rows["totalItems"], 0)

    def test_ingest_and_reader_cannot_run_assessments(self):
        for role in ("ingest", "reader"):
            with self.subTest(role=role), self.assertRaises(PocketBaseError) as error:
                self.clients[role].claim_assessment_job()
            self.assertEqual(error.exception.status, 403)

    def test_sensor_commands_queue_and_run_assessments(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"), POCKETBASE_URL=self.url, POCKETBASE_TOKEN=self.worker.token)
        command = [sys.executable, "-m", "astrocrates", "capture", "--interval", "0", "--process",
                   "--assessment-policy", str(root / "config/assessment-demo.json"), "--run-assessment"]
        output = subprocess.check_output(command, env=env, cwd=root, text=True)
        ticks = [json.loads(line) for line in output.splitlines()]
        self.assertTrue(all(tick["assessment_status"] == "completed" for tick in ticks))
        self.assertEqual(len(self.worker.list_assessment_jobs(status="complete")), 21)
        self.assertEqual(len(self.worker.get_assessments("a")), 7)
        self.assertTrue(self.worker.list_escalations())
        replay = subprocess.check_output(command, env=env, cwd=root, text=True)
        self.assertTrue(all(json.loads(line)["assessment_status"] == "no_new_data" for line in replay.splitlines()))
        self.assertEqual(len(self.worker.list_assessment_jobs(status="complete")), 21)


if __name__ == "__main__":
    unittest.main()
