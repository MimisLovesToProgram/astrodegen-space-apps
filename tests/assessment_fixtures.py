"""Synthetic test rules exercise engine mechanics, not medical thresholds."""

from assessment.policy import DOMAINS


def sample_policy():
    return {"schema_version": "astrocrates.assessment-policy.v1", "policy_id": "test-v1",
            "purpose": "synthetic_demo", "simulation_only": True, "source": "sensor",
            "max_age_seconds": 172800,
            "domains": {name: {"rules": [{"id": name + "-test", "metric": "hr_resting", "feature": "value",
                                         "operator": "gt", "threshold": 80, "points": 70, "level": 2}],
                                "bands": [{"min_points": 0, "level": 0}, {"min_points": 20, "level": 1},
                                          {"min_points": 50, "level": 2}, {"min_points": 80, "level": 3}]}
                        for name in DOMAINS}}


def observation(value=60, day=5, metric="hr_resting", **changes):
    result = {"astronaut_id": "a", "metric": metric, "source": "sensor", "unit": "bpm",
              "captured_at": f"2026-11-{day:02d}T12:00:00Z", "value": value,
              "context": {"simulated": True}, "quality_flags": []}
    result.update(changes)
    return result
