"""Evaluate calendar-day and elapsed-time features from explicit observations."""

from datetime import datetime, timedelta, timezone

from .features import feature_value


def timestamp(item):
    return datetime.fromisoformat(item["captured_at"].replace("Z", "+00:00")).astimezone(timezone.utc)


def daily_readings(readings):
    # We keep the last observation of each UTC day so a burst of readings
    # cannot count as several consecutive days or dominate a daily baseline.
    days = {}
    for item in readings:
        days[timestamp(item).date()] = item
    return [days[day] for day in sorted(days)]


def evaluate_feature(rule, readings, index, streams, as_of):
    feature = rule["feature"]
    item = readings[index]
    if feature == "contains_any":
        return {"value": int(bool(set(item["value"]) & set(rule["matches"]))), "samples_used": 1}
    if feature == "hours_since_true":
        prefix = readings[:index + 1]
        last_true = next((i for i in range(len(prefix) - 1, -1, -1) if prefix[i]["value"] is True), None)
        # We require continuous reporting. Missing logs are unknown, rather
        # than evidence that no interaction or exercise occurred.
        relevant = prefix[last_true:] if last_true is not None else prefix
        clocks = [timestamp(value) for value in relevant]
        gap = rule.get("max_gap_seconds", 129600)
        if any((b - a).total_seconds() > gap for a, b in zip(clocks, clocks[1:])):
            return {"value": None, "reason": "sampling_gap"}
        if (as_of - clocks[-1]).total_seconds() > gap:
            return {"value": None, "reason": "sampling_gap"}
        elapsed = (as_of - clocks[0]).total_seconds() / 3600
        if last_true is None and elapsed <= rule["threshold"]:
            return {"value": None, "reason": "unknown_last_positive"}
        return {"value": elapsed, "samples_used": len(relevant), "is_lower_bound": last_true is None}
    if feature == "missed_mission_days":
        mission = {timestamp(value).date(): value["value"] for value in streams.get("mission_day", [])}
        by_day = {timestamp(value).date(): value for value in readings[:index + 1]}
        day = timestamp(item).date()
        last = mission.get(day)
        if type(last) is not int or last < 1:
            return {"value": None, "reason": "missing_mission_day"}
        count = 0
        for offset in range(last):
            expected = day - timedelta(days=offset)
            if expected not in by_day or mission.get(expected) != last - offset:
                return {"value": None, "reason": "incomplete_mission_history"}
            count += by_day[expected]["value"] is False
        return {"value": count, "samples_used": last}
    window = rule.get("window_days", rule.get("window", 3))
    if "window_days" in rule:
        prefix = daily_readings(readings[:index + 1])
        current = timestamp(item).date()
        expected = [current - timedelta(days=i) for i in range(window, 0, -1)]
        by_day = {timestamp(value).date(): value for value in prefix}
        if any(day not in by_day for day in expected):
            return {"value": None, "reason": "insufficient_calendar_baseline"}
        selected = [by_day[day] for day in expected] + [item]
        return feature_value(selected, window, feature, window)
    return feature_value(readings, index, feature, window)
