"""Create and persist data-quality alerts without assigning medical risk."""

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime

from .storage import connect_database
from .validation import json_string, utc_string


ALERT_KINDS = {"missing", "stale", "future", "sampling_gap"}


def _key(value):
    return hashlib.sha256(json_string(value).encode()).hexdigest()


def alert_snapshot(report, policy_name="default"):
    """Describe the active conditions for one crew and monitoring policy."""
    if not isinstance(policy_name, str) or not policy_name.strip() or len(policy_name) > 100:
        raise ValueError("policy_name must contain 1 to 100 characters")
    sampling = report.get("sampling", {})
    policy = {"name": policy_name, "max_age_seconds": report["max_age_seconds"],
              "metrics": sorted(row["metric"] for row in report["metrics"]),
              "source": report["source"], "history_limit": report["history_limit"],
              "expected_interval_seconds": sampling.get("expected_interval_seconds"),
              "gap_tolerance_fraction": sampling.get("tolerance_fraction")}
    # We isolate policies so a daily replay cannot resolve a live-stream alert.
    policy_key = _key(policy)
    scope_key = _key([policy_key, report["astronaut_id"]])
    alerts = [{"metric": row["metric"], "source": report["source"] or "",
               "kind": row["status"], "evidence": row}
              for row in report["metrics"] if row["status"] in {"missing", "stale", "future"}]
    # We alert on currently overdue streams; past gaps remain informational
    # after a device starts producing fresh data again.
    alerts.extend({"metric": row["metric"], "source": row["source"],
                   "kind": "sampling_gap", "evidence": row}
                  for row in sampling.get("overdue_streams", []))
    for alert in alerts:
        alert["alert_key"] = _key([scope_key, alert["metric"], alert["source"], alert["kind"]])
    if len(alerts) > 500:
        raise ValueError("A check can contain at most 500 alerts; narrow its scope")
    return {"scope_key": scope_key, "policy_key": policy_key, "policy_name": policy_name,
            "policy": policy, "astronaut_id": report["astronaut_id"],
            "checked_at": report["reference_time"],
            "history_may_be_truncated": report["history_may_be_truncated"], "alerts": alerts}


def validate_snapshot(snapshot):
    """Reject malformed snapshots before starting a storage transaction."""
    timestamp = datetime.fromisoformat(snapshot["checked_at"].replace("Z", "+00:00"))
    if utc_string(timestamp) != snapshot["checked_at"]:
        raise ValueError("checked_at must use canonical UTC microseconds")
    if not snapshot["astronaut_id"] or len(snapshot["alerts"]) > 500:
        raise ValueError("Invalid quality-check scope or alert count")
    # We derive keys from content rather than let a malformed snapshot update
    # another policy's records.
    if snapshot["policy_key"] != _key(snapshot["policy"]) or snapshot["scope_key"] != _key([snapshot["policy_key"], snapshot["astronaut_id"]]):
        raise ValueError("Quality-check keys do not match the policy and crew")
    seen = set()
    for alert in snapshot["alerts"]:
        key = _key([snapshot["scope_key"], alert["metric"], alert["source"], alert["kind"]])
        if alert["kind"] not in ALERT_KINDS or alert["alert_key"] != key or key in seen:
            raise ValueError("Invalid or repeated alert identity")
        seen.add(key)
    json_string(snapshot)


def save_quality_alerts(snapshot, db_path="data/telemetry.sqlite"):
    validate_snapshot(snapshot)
    scope, checked = snapshot["scope_key"], snapshot["checked_at"]
    result = {"scope_key": scope, "opened": 0, "reopened": 0, "resolved": 0,
              "active": 0, "ignored_older_report": False}
    with closing(connect_database(db_path)) as connection:
        with connection:
            # We commit the entire check together so concurrent monitors cannot
            # create duplicate alerts or partially resolve earlier conditions.
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute("SELECT checked_at FROM quality_checks WHERE scope_key=?", (scope,)).fetchone()
            if previous and previous[0] > checked:
                result["ignored_older_report"] = True
            else:
                _apply_snapshot(connection, snapshot, result)
            result["active"] = connection.execute(
                "SELECT count(*) FROM quality_alerts WHERE scope_key=? AND status='active'", (scope,)).fetchone()[0]
    return result


def _apply_snapshot(connection, snapshot, result):
    scope, checked = snapshot["scope_key"], snapshot["checked_at"]
    active = {row[0] for row in connection.execute(
        "SELECT alert_key FROM quality_alerts WHERE scope_key=? AND status='active'", (scope,))}
    incoming = {alert["alert_key"] for alert in snapshot["alerts"]}
    for alert in snapshot["alerts"]:
        existing = connection.execute("SELECT status FROM quality_alerts WHERE alert_key=?", (alert["alert_key"],)).fetchone()
        if existing is None:
            connection.execute("""INSERT INTO quality_alerts
                (alert_key,scope_key,policy_name,astronaut_id,metric,source,kind,status,
                 first_detected_at,last_checked_at,resolved_at,occurrences,evidence_json)
                VALUES (?,?,?,?,?,?,?,'active',?,?,NULL,1,?)""",
                (alert["alert_key"], scope, snapshot["policy_name"], snapshot["astronaut_id"],
                 alert["metric"], alert["source"], alert["kind"], checked, checked,
                 json_string(alert["evidence"])))
            result["opened"] += 1
        else:
            # We count another episode only after a resolved alert reappears.
            reopening = existing[0] == "resolved"
            connection.execute("""UPDATE quality_alerts SET status='active',last_checked_at=?,
                resolved_at=NULL,occurrences=occurrences+?,evidence_json=? WHERE alert_key=?""",
                (checked, int(reopening), json_string(alert["evidence"]), alert["alert_key"]))
            result["reopened"] += int(reopening)
    for key in active - incoming:
        connection.execute("""UPDATE quality_alerts SET status='resolved',resolved_at=?,
            last_checked_at=? WHERE alert_key=?""", (checked, checked, key))
        result["resolved"] += 1
    connection.execute("""INSERT INTO quality_checks
        (scope_key,policy_key,policy_name,astronaut_id,checked_at,policy_json)
        VALUES (?,?,?,?,?,?) ON CONFLICT(scope_key) DO UPDATE SET checked_at=excluded.checked_at""",
        (scope, snapshot["policy_key"], snapshot["policy_name"], snapshot["astronaut_id"], checked,
         json_string(snapshot["policy"])))


def list_quality_alerts(db_path="data/telemetry.sqlite", *, status="active", astronaut_id=None,
                        policy_name=None, limit=100):
    if status not in {"active", "resolved", "all"} or type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError("Use status active/resolved/all and an integer limit between 1 and 10000")
    conditions, parameters = [], []
    for column, value in (("status", None if status == "all" else status),
                          ("astronaut_id", astronaut_id), ("policy_name", policy_name)):
        if value is not None:
            conditions.append(column + "=?")
            parameters.append(value)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with closing(connect_database(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM quality_alerts" + where +
                                  " ORDER BY last_checked_at DESC,alert_key LIMIT ?", (*parameters, limit)).fetchall()
    alerts = []
    for row in rows:
        alert = dict(row)
        alert["evidence"] = json.loads(alert.pop("evidence_json"))
        alerts.append(alert)
    return alerts
