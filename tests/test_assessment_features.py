"""Verify baseline isolation, time-based trends, and missing-data behavior."""

import unittest

from assessment.features import feature_value


def series(values, days=None):
    return [{"value": value, "captured_at": f"2026-11-{day:02d}T12:00:00Z"}
            for value, day in zip(values, days or range(1, len(values) + 1))]


class FeatureTests(unittest.TestCase):
    def test_baseline_excludes_the_current_and_future_values(self):
        readings = series([60, 62, 64, 93, 200])
        result = feature_value(readings, 3, "baseline_change_pct", 3)
        self.assertEqual(result["baseline"], 62)
        self.assertEqual(result["value"], 50)
        self.assertEqual(result["samples_used"], 3)

    def test_trend_uses_elapsed_time(self):
        # We use irregular intervals to distinguish a per-day slope from a
        # misleading change-per-sample calculation.
        result = feature_value(series([10, 14, 22], [1, 3, 7]), 2, "trend_per_day", 3)
        self.assertAlmostEqual(result["value"], 2)

    def test_missing_or_flat_baselines_do_not_produce_infinite_scores(self):
        self.assertIsNone(feature_value(series([60, 65]), 1, "baseline_change", 3)["value"])
        self.assertEqual(feature_value(series([60, 60, 60, 60]), 3, "mad_deviation", 3)["value"], 0)
        self.assertIsNone(feature_value(series([60, 60, 60, 80]), 3, "mad_deviation", 3)["value"])
        self.assertIsNone(feature_value(series([0, 0, 0, 10]), 3, "baseline_change_pct", 3)["value"])

    def test_boolean_and_symptom_features_keep_their_types(self):
        self.assertIs(feature_value(series([False]), 0)["value"], False)
        self.assertEqual(feature_value(series([["fatigue", "headache"]]), 0, "count")["value"], 2)
        self.assertIsNone(feature_value(series([False, True, False]), 2, "trend_per_day", 3)["value"])

    def test_overflow_is_reported_as_unavailable(self):
        result = feature_value(series([-1e308, -1e308, 1e308]), 2, "baseline_change", 2)
        self.assertIsNone(result["value"])
        self.assertEqual(result["reason"], "numeric_overflow")
