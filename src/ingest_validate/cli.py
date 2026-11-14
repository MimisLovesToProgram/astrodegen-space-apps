"""Run from the repository root with:

PYTHONPATH=src python3 -m ingest_validate.cli --demo

Use --input telemetry.json for a JSON array from Step 1, or --latest crew_01
for Step 3-ready history. The demo is synthetic and has stable identities so
repeating it demonstrates duplicate handling. No database is committed.
"""

import argparse
import json
import sys
from datetime import datetime

from .pipeline import process_sensor_packets, simulated_mission

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
    actions.add_argument("--sensor-demo", action="store_true", help="Run the complete synthetic biosensors mission")
    actions.add_argument("--sensor-input", metavar="JSONL_FILE", help="Read biosensors JSON Lines; use - for stdin")
    parser.add_argument("--assume-utc", action="store_true", help="Explicitly interpret naive sensor timestamps as UTC")
    parser.add_argument("--reference-time", help="Explicit aware ISO timestamp for replay validation")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    reference_time = None
    if args.reference_time:
        try:
            reference_time = datetime.fromisoformat(args.reference_time.replace("Z", "+00:00"))
            if reference_time.tzinfo is None:
                raise ValueError("Timezone required")
        except ValueError:
            parser.error("--reference-time must be an ISO timestamp with a timezone")
    if args.sensor_demo or args.sensor_input:
        if args.sensor_demo:
            packets, simulation_time = simulated_mission()
            output = process_sensor_packets(
                packets, args.db, assume_utc=True,
                reference_time=reference_time or simulation_time,
            )
            output["simulation_clock"] = (reference_time or simulation_time).isoformat()
        else:
            def packets_from_lines(handle):
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        yield json.loads(line)
                    except ValueError:
                        yield line.rstrip("\n")  # Preserve malformed deliveries for quarantine.
            if args.sensor_input == "-":
                output = process_sensor_packets(
                    packets_from_lines(sys.stdin), args.db,
                    assume_utc=args.assume_utc, reference_time=reference_time,
                )
            else:
                with open(args.sensor_input, encoding="utf-8") as handle:
                    output = process_sensor_packets(
                        packets_from_lines(handle), args.db,
                        assume_utc=args.assume_utc, reference_time=reference_time,
                    )
        output["counts"] = {key: len(records) for key, records in output["ingestion"].items()}
    elif args.latest:
        output = get_validated_observations(args.db, args.latest, args.limit)
    else:
        if args.demo:
            measurements = demo_measurements()
        else:
            with open(args.input, encoding="utf-8") as handle:
                measurements = json.load(handle)
            if not isinstance(measurements, list):
                parser.error("Input must be a JSON array of measurements")
        result = ingest_batch(measurements, args.db, reference_time=reference_time)
        output = {"counts": {key: len(records) for key, records in result.items()}, **result}
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
