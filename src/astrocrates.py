"""Astrocrates commands: capture sensors, process pending packets, read history."""

import argparse
import json
import math
import time
from datetime import datetime, timezone

from biosensors import Crew, noise_from, reading_from


class LocalTelemetry:
    """The same capture/worker/history interface for offline SQLite runs."""
    def __init__(self, db_path):
        self.db_path = db_path

    def capture(self, packet, **options):
        from ingest_validate.capture import capture_sensor_packets
        packet_id = capture_sensor_packets([packet], self.db_path, **options)[0]
        return {"id": packet_id, "status": "pending"}

    def process_pending(self, limit=100):
        from ingest_validate.worker import validate_pending_packets
        return validate_pending_packets(self.db_path, limit=limit)

    def get_history(self, astronaut_id, limit=250, *, source=None):
        from ingest_validate.service import get_validated_observations
        return get_validated_observations(self.db_path, astronaut_id, limit, source=source)

    def get_audit_summary(self):
        from contextlib import closing
        from ingest_validate.storage import connect_database
        with closing(connect_database(self.db_path)) as connection:
            # Sensor-linked rows use the original packet's source. Canonical
            # inputs outside the adapter retain their own source label.
            rows = connection.execute("""SELECT
                COALESCE(p.source, CASE WHEN r.payload_encoding='json' AND json_valid(r.payload)
                  THEN json_extract(r.payload, '$.source') END, 'unknown') AS source,
                r.status, count(*) FROM raw_measurements r
                LEFT JOIN sensor_packets p ON p.id=r.sensor_packet_id GROUP BY 1, 2""").fetchall()
            packets = dict(connection.execute("SELECT status,count(*) FROM sensor_packets GROUP BY status").fetchall())
        return {"packets": {"pending": packets.get("pending", 0), "processed": packets.get("processed", 0)},
                "results": [{"source": row[0], "status": row[1], "total": row[2]} for row in rows]}

    def save_quality_alerts(self, snapshot):
        from ingest_validate.alerts import save_quality_alerts
        return save_quality_alerts(snapshot, self.db_path)

    def list_quality_alerts(self, **options):
        from ingest_validate.alerts import list_quality_alerts
        return list_quality_alerts(self.db_path, **options)


def sensor_batches(mode="story", ticks=None):
    """Yield one bounded crew tick, its validation clock, and UTC assumption.

    Existing story data is unchanged and uses its explicit synthetic UTC clock.
    Noise timestamps are interpreted in the generator machine's local timezone
    and converted to aware UTC before capture. No timezone guess is made for
    externally supplied packets.
    """
    if mode not in ("story", "noise"):
        raise ValueError("mode must be story or noise")
    if ticks is not None and (type(ticks) is not int or ticks < 1):
        raise ValueError("ticks must be a positive integer")
    if mode == "story":
        days = min(len(arc) for arc in Crew.values())
        if ticks is not None and ticks > days:
            raise ValueError(f"The story has only {days} ticks")
        for day in range(1, (ticks if ticks is not None else days) + 1):
            packets = [reading_from(crew, arc[day - 1], day) for crew, arc in Crew.items()]
            clock = datetime.fromisoformat(packets[0]["timestamp"]).replace(tzinfo=timezone.utc)
            yield packets, clock, True
    else:
        tick = 0
        while ticks is None or tick < ticks:
            packets = [noise_from(crew, tick) for crew in Crew]
            for packet in packets:
                packet["timestamp"] = datetime.fromisoformat(packet["timestamp"]).astimezone(timezone.utc).isoformat()
            yield packets, None, False
            tick += 1


def report_processed(store, result, assessment_policy=None, assessment_history_limit=10000, run_assessment=False):
    # We export clean history and run assessment only with an explicit policy.
    ingestion = result["ingestion"]
    crew = sorted({item["astronaut_id"] for item in ingestion["accepted"]})
    output = {
        "processed_packets": len(result["packet_ids"]),
        "counts": {key: len(records) for key, records in ingestion.items()},
        "step3_history": {astronaut: store.get_history(astronaut) for astronaut in crew},
        "assessment_status": "not_configured",
    }
    if assessment_policy is not None:
        from assessment.jobs import run_jobs
        queued = []
        for astronaut in crew:
            # We reassess the latest clean state even when a newly accepted
            # reading arrived late and changes the preceding baseline window.
            history = store.get_history(astronaut, assessment_history_limit)
            # We keep a real check-in on the real clock even if this demo
            # database also contains future-dated synthetic mission readings.
            real_input = any(item["astronaut_id"] == astronaut and item.get("context", {}).get("simulated") is not True
                             for item in ingestion["accepted"])
            clock = datetime.now(timezone.utc) if real_input else max(
                datetime.fromisoformat(item["captured_at"].replace("Z", "+00:00")) for item in history)
            queued.append(store.enqueue_assessment(history, astronaut, assessment_policy,
                                                   as_of=clock, history_limit=assessment_history_limit))
        output["assessment_jobs"] = queued
        output["assessment_status"] = "queued" if queued else "no_new_data"
        if run_assessment and queued:
            work = [run_jobs(store, job_id=job["id"]) for job in queued]
            output["assessment_work"] = work
            output["assessment_status"] = "failed" if any(item["failed"] for item in work) else "completed"
    return output


def main():
    parser = argparse.ArgumentParser(description="Astrocrates sensor and validation pipeline")
    parser.add_argument("--backend", choices=("pocketbase", "sqlite"), default="pocketbase")
    parser.add_argument("--db", default="data/telemetry.sqlite", help="SQLite development database")
    parser.add_argument("--env-file", help="PocketBase settings file; default is .env in the current directory")
    actions = parser.add_subparsers(dest="action", required=True)
    # Capture, validation, monitoring, and handoff are separate commands so
    # the same workflow can run interactively or as independent processes.
    capture = actions.add_parser("capture", help="Step 1: save original timestamped packets before validation")
    capture.add_argument("--mode", choices=("story", "noise"), default="story")
    capture.add_argument("--ticks", type=int, help="Default: seven story ticks or continuous noise")
    capture.add_argument("--interval", type=float, default=3)
    capture.add_argument("--process", action="store_true", help="Run Step 2 after each saved tick")
    process = actions.add_parser("process", help="Step 2: process a bounded pending batch")
    process.add_argument("--limit", type=int, default=100)
    process.add_argument("--watch", action="store_true")
    process.add_argument("--interval", type=float, default=1)
    for command in (capture, process):
        command.add_argument("--assessment-policy", help="Queue Step 3 using an explicit policy JSON")
        command.add_argument("--assessment-history-limit", type=int, default=10000)
        command.add_argument("--run-assessment", action="store_true", help="Run the queued Step 3 work immediately")
    history = actions.add_parser("history", help="Read validated observations for Step 3")
    history.add_argument("astronaut_id")
    history.add_argument("--limit", type=int, default=250)
    quality = actions.add_parser("quality", help="Report missing/stale measurements and data acceptance rates")
    quality.add_argument("astronaut_id")
    quality.add_argument("--max-age-seconds", type=float, required=True)
    quality.add_argument("--reference-time", help="Explicit aware timestamp for a synthetic replay")
    quality.add_argument("--history-limit", type=int, default=10000)
    quality.add_argument("--metrics", nargs="+", help="Expected metric names; default is the full simulator schema")
    quality.add_argument("--source", help="Check a specific sensor source")
    quality.add_argument("--expected-interval-seconds", type=float, help="Explicit sampling cadence for gap checks")
    quality.add_argument("--gap-tolerance-fraction", type=float, default=0.1)
    actions.add_parser("contract", help="Show the versioned Step 1/2/3 data contract")
    handoff = actions.add_parser("handoff", help="Export versioned clean history for Step 3")
    handoff.add_argument("astronaut_id")
    handoff.add_argument("--limit", type=int, default=250)
    from assessment.cli import COMMANDS as ASSESSMENT_COMMANDS, execute as execute_assessment, register_commands
    register_commands(actions)
    from ingest_validate.monitor import COMMANDS as MONITOR_COMMANDS, execute as execute_monitor, register_commands as register_monitor
    register_monitor(actions)
    args = parser.parse_args()
    if hasattr(args, "interval") and (not math.isfinite(args.interval) or args.interval < 0):
        parser.error("--interval must be finite and nonnegative")
    if args.action in {"process", "assessment-worker", "monitor"} and args.watch and args.interval == 0:
        parser.error("--watch requires a positive --interval")
    if args.action == "contract":
        from ingest_validate.contract import observation_contract
        print(json.dumps(observation_contract(), indent=2, allow_nan=False))
        return
    if args.action in ASSESSMENT_COMMANDS and args.backend != "pocketbase":
        parser.error("Assessment persistence uses the shared PocketBase backend; import assessment for offline calculations")
    assessment_policy = None
    if args.action in {"capture", "process"}:
        if args.run_assessment and not args.assessment_policy:
            parser.error("--run-assessment requires --assessment-policy")
        if args.assessment_policy:
            if args.backend != "pocketbase" or (args.action == "capture" and not args.process):
                parser.error("Automatic assessment requires PocketBase and capture --process or the process command")
            from assessment.policy import load_policy
            assessment_policy = load_policy(args.assessment_policy)
    if args.backend == "pocketbase":
        # The command interface is shared by both storage implementations;
        # database credentials are resolved only for the HTTP backend.
        from ingest_validate.pocketbase import PocketBaseTelemetry
        store = PocketBaseTelemetry.from_environment(args.env_file)
    else:
        store = LocalTelemetry(args.db)
    try:
        if args.action in MONITOR_COMMANDS:
            execute_monitor(args, store)
        elif args.action in ASSESSMENT_COMMANDS:
            execute_assessment(args, store)
        elif args.action == "capture":
            for tick, (packets, clock, assume_utc) in enumerate(sensor_batches(args.mode, args.ticks)):
                if tick:
                    time.sleep(args.interval)
                ids = [store.capture(packet, assume_utc=assume_utc, reference_time=clock)["id"] for packet in packets]
                output = {"captured_packets": len(ids), "packet_ids": ids,
                          "simulation_clock": clock.isoformat() if clock else None}
                if args.process:
                    output.update(report_processed(store, store.process_pending(), assessment_policy,
                                                   args.assessment_history_limit, args.run_assessment))
                print(json.dumps(output, allow_nan=False), flush=True)
        elif args.action == "process":
            while True:
                result = store.process_pending(args.limit)
                if result["packet_ids"] or not args.watch:
                    print(json.dumps(report_processed(store, result, assessment_policy,
                                                     args.assessment_history_limit, args.run_assessment), allow_nan=False), flush=True)
                if not args.watch:
                    break
                time.sleep(args.interval)
        elif args.action == "quality":
            from ingest_validate.quality import quality_report, summarize_audit
            reference = datetime.fromisoformat(args.reference_time.replace("Z", "+00:00")) if args.reference_time else None
            output = quality_report(store.get_history(args.astronaut_id, args.history_limit, source=args.source), args.astronaut_id,
                                    max_age_seconds=args.max_age_seconds, reference_time=reference,
                                    expected_metrics=args.metrics, history_limit=args.history_limit,
                                    source=args.source, expected_interval_seconds=args.expected_interval_seconds,
                                    gap_tolerance_fraction=args.gap_tolerance_fraction)
            output["audit"] = summarize_audit(store.get_audit_summary())
            print(json.dumps(output, indent=2, allow_nan=False))
        elif args.action == "handoff":
            from ingest_validate.contract import history_handoff
            observations = store.get_history(args.astronaut_id, args.limit)
            print(json.dumps(history_handoff(args.astronaut_id, observations, args.limit), indent=2, allow_nan=False))
        else:
            print(json.dumps(store.get_history(args.astronaut_id, args.limit), indent=2, allow_nan=False))
    except KeyboardInterrupt:
        pass  # Previously committed captures/results remain durable.


if __name__ == "__main__":
    main()
