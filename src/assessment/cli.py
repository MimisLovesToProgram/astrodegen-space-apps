"""Register Step 3 commands without mixing them into sensor generation."""

import json
import time
from datetime import datetime

from .jobs import run_jobs
from .policy import load_policy


COMMANDS = {"assess", "assessment-worker", "assessments", "assessment-jobs", "retry-assessment", "escalations"}


def register_commands(actions):
    assess = actions.add_parser("assess", help="Queue and run a configured assessment of clean crew history")
    assess.add_argument("astronaut_id")
    assess.add_argument("--policy", required=True, help="Explicit assessment policy JSON; no hidden defaults")
    assess.add_argument("--history-limit", type=int, default=10000)
    period = assess.add_mutually_exclusive_group()
    period.add_argument("--reference-time", help="Aware ISO timestamp for a single assessment")
    period.add_argument("--all-days", action="store_true", help="Backfill one assessment per UTC history day")
    assess.add_argument("--queue-only", action="store_true")
    worker = actions.add_parser("assessment-worker", help="Process durable assessment jobs")
    worker.add_argument("--limit", type=int, default=100)
    worker.add_argument("--lease-seconds", type=int, default=30)
    worker.add_argument("--watch", action="store_true")
    worker.add_argument("--interval", type=float, default=1)
    history = actions.add_parser("assessments", help="Read stored crew assessments")
    history.add_argument("astronaut_id")
    history.add_argument("--limit", type=int, default=250)
    jobs = actions.add_parser("assessment-jobs", help="Inspect durable work and failures")
    jobs.add_argument("--status", choices=("pending", "running", "complete", "failed"))
    jobs.add_argument("--limit", type=int, default=100)
    retry = actions.add_parser("retry-assessment", help="Retry a failed job without re-ingesting sensor data")
    retry.add_argument("job_id")
    retry.add_argument("--reset-attempts", action="store_true")
    events = actions.add_parser("escalations", help="Read stored orange/red transition events")
    events.add_argument("--astronaut-id")
    events.add_argument("--limit", type=int, default=100)


def execute(args, store):
    if args.action == "assess":
        policy = load_policy(args.policy)
        history = store.get_history(args.astronaut_id, args.history_limit)
        if args.all_days:
            # We make backfills explicit and evaluate each day only against
            # data captured by that day's end, without future-data leakage.
            clocks = [datetime.fromisoformat(day + "T23:59:59.999999+00:00")
                      for day in sorted({item["captured_at"][:10] for item in history})]
        else:
            clocks = [datetime.fromisoformat(args.reference_time.replace("Z", "+00:00")) if args.reference_time else None]
        queued = [store.enqueue_assessment(history, args.astronaut_id, policy, as_of=clock,
                                           history_limit=args.history_limit) for clock in clocks]
        outcomes = [run_jobs(store, job_id=job["id"]) for job in queued] if not args.queue_only else []
        output = {"queued": queued, "completed": sum(len(item["completed"]) for item in outcomes),
                  "failed": [job for item in outcomes for job in item["failed"]],
                  "escalation_events": sum(item["escalation_events"] for item in outcomes),
                  "policy_id": policy["policy_id"], "policy_purpose": policy["purpose"]}
    elif args.action == "assessment-worker":
        while True:
            output = run_jobs(store, limit=args.limit, lease_seconds=args.lease_seconds)
            if output["completed"] or output["failed"] or not args.watch:
                print(json.dumps(output, allow_nan=False), flush=True)
            if not args.watch:
                return
            time.sleep(args.interval)
    elif args.action == "assessments":
        output = store.get_assessments(args.astronaut_id, args.limit)
    elif args.action == "assessment-jobs":
        output = store.list_assessment_jobs(status=args.status, limit=args.limit)
    elif args.action == "retry-assessment":
        output = store.retry_assessment_job(args.job_id, reset_attempts=args.reset_attempts)
    else:
        output = store.list_escalations(astronaut_id=args.astronaut_id, limit=args.limit)
    print(json.dumps(output, indent=2, allow_nan=False))
