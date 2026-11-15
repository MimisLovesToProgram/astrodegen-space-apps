// We apply complete monitoring snapshots in one transaction. These alerts
// describe data availability and timing, not an astronaut's health risk.
routerAdd("POST", "/api/astrocrates/quality-alerts", (e) => {
  if (e.auth.getString("role") !== "worker") {
    throw new ForbiddenError("Quality monitoring requires a worker service");
  }
  const body = e.requestInfo().body;
  const keyPattern = /^[a-f0-9]{64}$/;
  const timePattern = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$/;
  if (!keyPattern.test(body.scope_key || "") || !keyPattern.test(body.policy_key || "") ||
      typeof body.astronaut_id !== "string" || !body.astronaut_id ||
      typeof body.policy_name !== "string" || !body.policy_name.trim() ||
      !timePattern.test(body.checked_at || "") || !Number.isFinite(Date.parse(body.checked_at)) ||
      !Array.isArray(body.alerts) || body.alerts.length > 500 || !body.policy) {
    throw new BadRequestError("Invalid monitoring snapshot");
  }
  const incoming = {};
  for (const alert of body.alerts) {
    if (!keyPattern.test(alert.alert_key || "") || incoming[alert.alert_key] ||
        !["missing", "stale", "future", "sampling_gap"].includes(alert.kind) ||
        typeof alert.metric !== "string" || !alert.metric || typeof alert.source !== "string") {
      throw new BadRequestError("Invalid or repeated alert identity");
    }
    incoming[alert.alert_key] = true;
  }
  const result = {scope_key: body.scope_key, opened: 0, reopened: 0,
                  resolved: 0, active: 0, ignored_older_report: false};
  $app.runInTransaction((tx) => {
    const prior = tx.findRecordsByFilter("quality_checks", "scope_key={:scope}", "", 1, 0,
                                        {scope: body.scope_key});
    const active = tx.findRecordsByFilter("quality_alerts", "scope_key={:scope} && status='active'",
                                         "", 500, 0, {scope: body.scope_key});
    // We reject an older check before it can undo a newer recovery decision.
    if (prior.length && prior[0].getString("checked_at") > body.checked_at) {
      result.ignored_older_report = true;
      result.active = active.length;
      return;
    }
    for (const alert of body.alerts) {
      const matches = tx.findRecordsByFilter("quality_alerts", "alert_key={:key}", "", 1, 0,
                                             {key: alert.alert_key});
      let record;
      if (!matches.length) {
        record = new Record(tx.findCollectionByNameOrId("quality_alerts"));
        record.load({alert_key: alert.alert_key, scope_key: body.scope_key,
          policy_name: body.policy_name, astronaut_id: body.astronaut_id,
          metric: alert.metric, source: alert.source, kind: alert.kind,
          first_detected_at: body.checked_at, occurrences: 1});
        result.opened++;
      } else {
        record = matches[0];
        if (record.getString("scope_key") !== body.scope_key) {
          throw new BadRequestError("Alert identity belongs to another monitoring scope");
        }
        // We count a new episode only when a resolved condition reappears.
        if (record.getString("status") === "resolved") {
          record.set("occurrences", record.getInt("occurrences") + 1);
          result.reopened++;
        }
      }
      record.load({status: "active", last_checked_at: body.checked_at,
                   resolved_at: "", evidence: alert.evidence});
      tx.save(record);
    }
    for (const record of active) {
      if (!incoming[record.getString("alert_key")]) {
        record.load({status: "resolved", resolved_at: body.checked_at, last_checked_at: body.checked_at});
        tx.save(record);
        result.resolved++;
      }
    }
    const checkpoint = prior.length ? prior[0] : new Record(tx.findCollectionByNameOrId("quality_checks"));
    checkpoint.load({scope_key: body.scope_key, policy_key: body.policy_key,
      policy_name: body.policy_name, astronaut_id: body.astronaut_id,
      checked_at: body.checked_at, policy: body.policy});
    tx.save(checkpoint);
    result.active = body.alerts.length;
  });
  return e.json(200, result);
}, $apis.requireAuth("telemetry_services"));
