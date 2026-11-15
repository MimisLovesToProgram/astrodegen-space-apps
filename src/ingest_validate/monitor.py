"""Poll quality conditions and persist state changes without external messages."""

import json
import time
from datetime import datetime

from .alerts import alert_snapshot
from .quality import quality_report


COMMANDS = {"monitor", "alerts"}


def register_commands(actions):
    monitor = actions.add_parser("monitor", help="Persist quality alerts and optionally check continuously")
    monitor.add_argument("astronaut_id")
    monitor.add_argument("--max-age-seconds", type=float, required=True)
    monitor.add_argument("--history-limit", type=int, default=10000)
    monitor.add_argument("--metrics", nargs="+")
    monitor.add_argument("--source")
    monitor.add_argument("--expected-interval-seconds", type=float)
    monitor.add_argument("--gap-tolerance-fraction", type=float, default=0.1)
    monitor.add_argument("--reference-time", help="Explicit clock for a single replay check")
    monitor.add_argument("--policy", default="default", help="Human-readable monitoring policy name")
    monitor.add_argument("--watch", action="store_true")
    monitor.add_argument("--interval", type=float, default=30)
    monitor.add_argument("--checks", type=int, help="Stop after this many checks in watch mode")
    alerts = actions.add_parser("alerts", help="Read active or resolved quality alerts")
    alerts.add_argument("--astronaut-id")
    alerts.add_argument("--policy")
    alerts.add_argument("--status", choices=("active", "resolved", "all"), default="active")
    alerts.add_argument("--limit", type=int, default=100)


def execute(args, store):
    if args.action == "alerts":
        print(json.dumps(store.list_quality_alerts(status=args.status, astronaut_id=args.astronaut_id,
                                                 policy_name=args.policy, limit=args.limit), indent=2, allow_nan=False))
        return
    if args.watch and args.reference_time:
        raise ValueError("Use a real clock with --watch; --reference-time is for a single replay check")
    if args.checks is not None and (not args.watch or args.checks < 1):
        raise ValueError("--checks requires --watch and a positive count")
    iteration = 0
    while True:
        reference = datetime.fromisoformat(args.reference_time.replace("Z", "+00:00")) if args.reference_time else None
        options = {"source": args.source} if args.source is not None else {}
        history = store.get_history(args.astronaut_id, args.history_limit, **options)
        report = quality_report(history, args.astronaut_id, max_age_seconds=args.max_age_seconds,
                                reference_time=reference, expected_metrics=args.metrics,
                                history_limit=args.history_limit, source=args.source,
                                expected_interval_seconds=args.expected_interval_seconds,
                                gap_tolerance_fraction=args.gap_tolerance_fraction)
        # We do not create missing-data claims from a window known to be cut
        # short when the expected metrics may simply be outside that window.
        if report["history_may_be_truncated"] and report["missing_metrics"]:
            raise ValueError("History may be truncated; increase its limit or narrow the source/metric scope")
        changes = store.save_quality_alerts(alert_snapshot(report, args.policy))
        if not args.watch or iteration == 0 or any(changes[key] for key in ("opened", "reopened", "resolved")):
            print(json.dumps({"quality": report, "alert_changes": changes}, allow_nan=False), flush=True)
        iteration += 1
        if not args.watch or (args.checks is not None and iteration >= args.checks):
            return
        time.sleep(args.interval)
