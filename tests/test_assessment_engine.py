"""Verify configured scores, unknown states, streaks, and reproducible inputs."""

import copy
import unittest
from datetime import datetime, timezone

from assessment import assess_history, validate_policy
from assessment_fixtures import observation, sample_policy


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.policy = sample_policy()
        self.clock = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)

    def test_configured_points_and_warning_levels(self):
        result = assess_history([observation(85)], "a", self.policy, as_of=self.clock)
        self.assertEqual(result["domains"]["immune"]["risk_score"], 70)
        self.assertEqual(result["domains"]["immune"]["level"], 2)
        self.assertEqual(result["metrics"]["hr_resting"]["level"], 2)
        self.assertEqual(result["overall_status"], "orange")
        self.assertEqual(result["policy_purpose"], "synthetic_demo")

    def test_missing_and_stale_data_are_not_green(self):
        for history in ([], [observation(60, day=1)]):
            result = assess_history(history, "a", self.policy, as_of=self.clock)
            self.assertIsNone(result["overall_level"])
            self.assertEqual(result["domains"]["immune"]["data_status"], "insufficient_data")
            self.assertIsNone(result["domains"]["immune"]["risk_score"])

    def test_future_readings_and_input_order_do_not_change_scores(self):
        history = [observation(60, day=4), observation(85)]
        result = assess_history(history, "a", self.policy, as_of=self.clock)
        other = assess_history(list(reversed(history)) + [observation(200, day=6)], "a", self.policy, as_of=self.clock)
        self.assertEqual(result["assessment_key"], other["assessment_key"])
        self.assertEqual(other["excluded_future_observations"], 1)

    def test_baseline_streak_uses_only_preceding_history(self):
        rule = self.policy["domains"]["cardiovascular"]["rules"][0]
        rule.update(feature="baseline_change_pct", threshold=10, window=3, consecutive=2,
                    min_span_seconds=86400, max_gap_seconds=172800)
        history = [observation(value, day=index + 1) for index, value in enumerate([60, 60, 60, 80, 80])]
        result = assess_history(history, "a", self.policy, as_of=self.clock)
        self.assertEqual(result["domains"]["cardiovascular"]["level"], 2)
        history.pop(3)
        result = assess_history(history, "a", self.policy, as_of=self.clock)
        self.assertIsNone(result["domains"]["cardiovascular"]["level"])

    def test_symptoms_and_boolean_rules(self):
        immune = self.policy["domains"]["immune"]["rules"][0]
        immune.update(metric="symptoms", feature="count", threshold=0)
        behavior = self.policy["domains"]["behavioral"]["rules"][0]
        behavior.update(metric="exercise_logged", operator="eq", threshold=False)
        result = assess_history([observation(), observation(["fatigue"], metric="symptoms", unit="list"),
                                 observation(False, metric="exercise_logged", unit="bool")],
                                "a", self.policy, as_of=self.clock)
        self.assertEqual(result["domains"]["immune"]["level"], 2)
        self.assertEqual(result["domains"]["behavioral"]["level"], 2)

    def test_simulation_policy_cannot_score_unmarked_real_data(self):
        with self.assertRaises(ValueError):
            assess_history([observation(context={})], "a", self.policy, as_of=self.clock)

    def test_conflicting_history_is_rejected(self):
        with self.assertRaises(ValueError):
            assess_history([observation(60), observation(90)], "a", self.policy, as_of=self.clock)

    def test_invalid_policies_fail_before_scoring(self):
        for field, value in (("points", -1), ("points", True), ("threshold", float("nan")),
                             ("feature", "typo"), ("consecutive", 0), ("unexpected", 1)):
            policy = copy.deepcopy(self.policy)
            policy["domains"]["immune"]["rules"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_policy(policy)
