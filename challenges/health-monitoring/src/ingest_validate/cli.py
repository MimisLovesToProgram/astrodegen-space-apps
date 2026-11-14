"""Run from the repository root with:

PYTHONPATH=challenges/health-monitoring/src python3 -m ingest_validate.cli --demo

Use --input telemetry.json for a JSON array from Step 1, or --latest crew_01
for Step 3-ready history. The demo is synthetic and has stable identities so
repeating it demonstrates duplicate handling. No database is committed.
"""

import argparse
import json

from .service import get_validated_observations, ingest_batch


def demo_measurements():
    common = {
        "astronaut_id": "crew_01", "captured_at": "2026-11-14T00:00:00Z",
        "source": "synthetic_demo_01", "context": {"simulated": True},
    }
    return [
        dict(common, metric=metric, value=value, unit=unit)
        for metric, value, unit in (
            ("hr_resting", 135, "bpm"), ("spo2", 97, "%"),
            ("temp_c", 100.6, "F"), ("spo2", 140, "%"),
            ("sleep_h", 420, "min"),
        )
    ]


def main():
    parser = argparse.ArgumentParser(description="Step 2 telemetry ingestion and validation")
    parser.add_argument("--db", default="data/telemetry.sqlite")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--demo", action="store_true", help="Ingest synthetic measurements")
    actions.add_argument("--input", help="Ingest a JSON array of measurements")
    actions.add_argument("--latest", metavar="ASTRONAUT_ID", help="Read validated history")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.latest:
        output = get_validated_observations(args.db, args.latest, args.limit)
    else:
        if args.demo:
            measurements = demo_measurements()
        else:
            with open(args.input, encoding="utf-8") as handle:
                measurements = json.load(handle)
            if not isinstance(measurements, list):
                parser.error("Input must be a JSON array of measurements")
        result = ingest_batch(measurements, args.db)
        output = {"counts": {key: len(records) for key, records in result.items()}, **result}
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
