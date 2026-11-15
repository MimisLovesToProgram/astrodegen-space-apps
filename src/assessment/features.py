"""Calculate rolling features without assigning health-risk thresholds."""

import math
import statistics
from datetime import datetime


def _number(value):
    try:
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        return False


def _finite_result(result):
    # We keep derived values JSON-safe even when individually finite inputs
    # overflow during subtraction, percentage change, or regression.
    if any(isinstance(value, (int, float)) and not isinstance(value, bool) and not _number(value)
           for value in result.values()):
        return {"value": None, "reason": "numeric_overflow"}
    return result


def feature_value(series, index, feature="value", window=3):
    """Return a feature and its provenance, or an explicit unavailable reason.

    series must contain one metric/source in chronological order. Baselines
    use earlier observations only; trend windows include the current reading.
    """
    current = series[index]["value"]
    if feature == "value":
        if not isinstance(current, bool) and not _number(current):
            return {"value": None, "reason": "non_numeric_value"}
        return {"value": current, "samples_used": 1}
    if feature == "count":
        if not isinstance(current, list):
            return {"value": None, "reason": "list_required"}
        return {"value": len(current), "samples_used": 1}
    if type(window) is not int or window < 2:
        raise ValueError("window must be an integer of at least two observations")
    if not _number(current):
        return {"value": None, "reason": "numeric_feature_required"}
    if feature in {"baseline_change", "baseline_change_pct", "mad_deviation"}:
        # We exclude the current reading from its baseline, so a new change
        # cannot move the reference against which we are evaluating it.
        previous = series[max(0, index - window):index]
        if len(previous) < window:
            return {"value": None, "reason": "insufficient_baseline", "samples_used": len(previous)}
        values = [item["value"] for item in previous]
        if not all(_number(value) for value in values):
            return {"value": None, "reason": "non_numeric_baseline"}
        baseline = statistics.median(values)
        deviation = statistics.median(abs(value - baseline) for value in values)
        if not _number(baseline) or not _number(deviation):
            return {"value": None, "reason": "numeric_overflow"}
        result = {"baseline": baseline, "mad": deviation, "samples_used": len(previous)}
        if feature == "baseline_change":
            result["value"] = current - baseline
        elif feature == "baseline_change_pct":
            if baseline == 0:
                return {**result, "value": None, "reason": "zero_baseline"}
            result["value"] = (current - baseline) / abs(baseline) * 100
        elif deviation == 0:
            # We do not emit infinity for a flat baseline. An unchanged value
            # has zero deviation; a changed value needs another feature rule.
            result["value"] = 0 if current == baseline else None
            if result["value"] is None:
                result["reason"] = "zero_variability_baseline"
        else:
            result["value"] = (current - baseline) / deviation
        return _finite_result(result)
    if feature == "trend_per_day":
        recent = series[max(0, index - window + 1):index + 1]
        if len(recent) < window or not all(_number(item["value"]) for item in recent):
            return {"value": None, "reason": "insufficient_trend", "samples_used": len(recent)}
        times = [datetime.fromisoformat(item["captured_at"].replace("Z", "+00:00")) for item in recent]
        # We fit against actual elapsed days, not sample indexes, so irregular
        # sampling does not masquerade as a faster or slower physiological trend.
        x = [(timestamp - times[0]).total_seconds() / 86400 for timestamp in times]
        y = [item["value"] for item in recent]
        mean_x, mean_y = statistics.mean(x), statistics.mean(y)
        denominator = sum((value - mean_x) ** 2 for value in x)
        if not denominator:
            return {"value": None, "reason": "identical_timestamps"}
        slope = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y)) / denominator
        return _finite_result({"value": slope, "samples_used": len(recent), "unit": "metric_units_per_day"})
    raise ValueError("Unsupported feature: " + feature)
