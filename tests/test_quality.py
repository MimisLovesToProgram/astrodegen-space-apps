"""Missing/stale data are quality findings, not health-risk classifications."""

import unittest
from datetime import datetime, timezone

from ingest_validate.quality import quality_report, sampling_gaps, summarize_audit


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.clock = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
        self.history = [
            {"astronaut_id": "a", "metric": "hr_resting", "value": 135,
             "captured_at": "2026-11-22T11:59:30Z"},
            {"astronaut_id": "a", "metric": "spo2", "value": 97,
             "captured_at": "2026-11-22T11:00:00Z"},
        ]

    def test_missing_stale_and_fresh_are_separate(self):
        report = quality_report(self.history, "a", max_age_seconds=60, reference_time=self.clock,
                                expected_metrics=["hr_resting", "spo2", "mood"])
        self.assertEqual(report["missing_metrics"], ["mood"])
        self.assertEqual(report["stale_metrics"], ["spo2"])
        self.assertEqual(report["fresh_metric_fraction"], 1 / 3)
        # High HR stays a fresh, valid observation; no clinical label is added.
        self.assertEqual(next(row for row in report["metrics"] if row["metric"] == "hr_resting")["status"], "fresh")

    def test_clock_mismatch_is_explicit_and_other_crews_do_not_fill_gaps(self):
        history = [{"astronaut_id": "a", "metric": "mood", "captured_at": "2026-11-23T00:00:00Z"},
                   {"astronaut_id": "b", "metric": "spo2", "captured_at": "2026-11-22T12:00:00Z"}]
        report = quality_report(history, "a", max_age_seconds=60, reference_time=self.clock,
                                expected_metrics=["mood", "spo2"], history_limit=2)
        self.assertEqual(report["future_metrics"], ["mood"])
        self.assertEqual(report["missing_metrics"], ["spo2"])
        self.assertTrue(report["history_may_be_truncated"])

    def test_age_policy_must_be_explicit_and_valid(self):
        for age in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(age=age), self.assertRaises(ValueError):
                quality_report([], "a", max_age_seconds=age, reference_time=self.clock)

    def test_retransmissions_do_not_inflate_acceptance_rate(self):
        # A source that repeats old packets should not receive a better
        # acceptance rate than a source delivering the same data once.
        report = summarize_audit({"packets": {"pending": 1, "processed": 3}, "results": [
            {"source": "sensor", "status": "accepted", "total": 3},
            {"source": "sensor", "status": "quarantined", "total": 1},
            {"source": "sensor", "status": "duplicate", "total": 100},
        ]})
        self.assertEqual(report["scope"], "all_database")
        self.assertEqual(report["sources"]["sensor"]["data_acceptance_rate"], 0.75)

    def test_sampling_gaps_keep_sources_separate(self):
        # We interleave two devices to ensure one cannot conceal the other's gap.
        history = [
            {"astronaut_id": "a", "metric": "hr_resting", "source": source,
             "captured_at": "2026-11-22T11:" + timestamp + "Z"}
            for source, timestamp in (("one", "57:00"), ("one", "59:00"),
                                      ("two", "58:00"), ("two", "59:00"), ("two", "59:00"))
        ]
        result = sampling_gaps(history, "a", expected_interval_seconds=60, reference_time=self.clock,
                               expected_metrics=["hr_resting"])
        self.assertEqual(result["stream_count"], 2)
        self.assertEqual(len(result["historical_gaps"]), 1)
        self.assertEqual(result["historical_gaps"][0]["source"], "one")
        self.assertEqual(result["overdue_streams"], [])

    def test_overdue_stream_and_source_filter(self):
        history = [{"astronaut_id": "a", "metric": "hr_resting", "source": "old",
                    "captured_at": "2026-11-22T11:58:00Z"},
                   {"astronaut_id": "a", "metric": "hr_resting", "source": "new",
                    "captured_at": "2026-11-22T12:00:00Z"}]
        result = quality_report(history, "a", max_age_seconds=60, reference_time=self.clock,
                                expected_metrics=["hr_resting"], source="old", expected_interval_seconds=60)
        self.assertEqual(result["stale_metrics"], ["hr_resting"])
        self.assertEqual(result["sampling"]["overdue_streams"][0]["source"], "old")

    def test_invalid_cadence_is_rejected(self):
        for interval in (0, -1, True, float("inf"), float("nan")):
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                sampling_gaps([], "a", expected_interval_seconds=interval, reference_time=self.clock,
                              expected_metrics=["hr_resting"])
