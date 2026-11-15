"""Durable assessment work using immutable policy and history snapshots."""

import hashlib
from datetime import datetime, timezone

from ingest_validate.validation import json_string, utc_string
from .engine import assess_history
from .policy import policy_digest, validate_policy


def make_job(history, astronaut_id, policy, *, as_of=None, history_limit=10000):
    policy = validate_policy(policy)
    if not isinstance(astronaut_id, str) or not astronaut_id.strip():
        raise ValueError("astronaut_id is required")
    if type(history_limit) is not int or not 1 <= history_limit <= 10000:
        raise ValueError("history_limit must be between 1 and 10000")
    clock = as_of if as_of is not None else datetime.now(timezone.utc)
    timestamp = utc_string(clock)
    observations = []
    for item in history:
        if not isinstance(item, dict):
            raise ValueError("History must contain normalized observation objects")
        if item.get("astronaut_id") == astronaut_id:
            captured = datetime.fromisoformat(item["captured_at"].replace("Z", "+00:00"))
            utc_string(captured)
            if captured <= clock:
                observations.append({**item, "captured_at": utc_string(captured)})
    if len(observations) > history_limit:
        raise ValueError("History exceeds the declared snapshot limit")
    # We freeze the inputs so a retry uses the same data even if more readings
    # arrive while the job is waiting. Input order does not create another job.
    observations.sort(key=json_string)
    digest = policy_digest(policy)
    key = hashlib.sha256(json_string([astronaut_id, digest, timestamp, observations]).encode()).hexdigest()
    return {"job_key": key, "astronaut_id": astronaut_id, "policy_digest": digest, "as_of": timestamp,
            "policy": policy, "observations": observations, "history_may_be_truncated": len(history) >= history_limit}


def run_jobs(store, *, limit=100, lease_seconds=30, job_id=None):
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    completed, failed, events = [], [], 0
    for _ in range(limit):
        job = store.claim_assessment_job(job_id=job_id, lease_seconds=lease_seconds)
        if job is None:
            break
        try:
            result = assess_history(job["observations"], job["astronaut_id"], job["policy"],
                                    as_of=datetime.fromisoformat(job["as_of"].replace("Z", "+00:00")))
            result["history_may_be_truncated"] = job["history_may_be_truncated"]
            outcome = store.complete_assessment_job(job["id"], job["claim_token"], result)
            completed.append({"job_id": job["id"], **outcome})
            events += outcome["events"]
        except Exception as error:
            # We record failure on the job instead of requiring duplicate sensor
            # ingestion. A later explicit retry can resume the frozen inputs.
            message = type(error).__name__ + ": " + str(error)
            store.fail_assessment_job(job["id"], job["claim_token"], message)
            failed.append({"job_id": job["id"], "error": message})
        if job_id is not None:
            break
    return {"completed": completed, "failed": failed, "escalation_events": events}
