// We store monitoring checkpoints and alert state separately from health risk.
migrate((app) => {
  const worker = '@request.auth.collectionName = "telemetry_services" && @request.auth.role = "worker"';
  const reader = '@request.auth.collectionName = "telemetry_services" && (@request.auth.role = "worker" || @request.auth.role = "reader")';
  app.save(new Collection({
    type: "base", name: "quality_checks", listRule: worker, viewRule: worker,
    createRule: null, updateRule: null, deleteRule: null,
    fields: [
      {name: "scope_key", type: "text", required: true, max: 64},
      {name: "policy_key", type: "text", required: true, max: 64},
      {name: "policy_name", type: "text", required: true, max: 100},
      {name: "astronaut_id", type: "text", required: true, max: 200},
      {name: "checked_at", type: "text", required: true, max: 100},
      {name: "policy", type: "json", required: true},
    ],
    indexes: ['CREATE UNIQUE INDEX idx_quality_check_scope ON quality_checks(scope_key)'],
  }));
  app.save(new Collection({
    type: "base", name: "quality_alerts", listRule: reader, viewRule: reader,
    createRule: null, updateRule: null, deleteRule: null,
    fields: [
      {name: "alert_key", type: "text", required: true, max: 64},
      {name: "scope_key", type: "text", required: true, max: 64},
      {name: "policy_name", type: "text", required: true, max: 100},
      {name: "astronaut_id", type: "text", required: true, max: 200},
      {name: "metric", type: "text", required: true, max: 100},
      {name: "source", type: "text", max: 200},
      {name: "kind", type: "select", required: true, maxSelect: 1,
       values: ["missing", "stale", "future", "sampling_gap"]},
      {name: "status", type: "select", required: true, maxSelect: 1, values: ["active", "resolved"]},
      {name: "first_detected_at", type: "text", required: true, max: 100},
      {name: "last_checked_at", type: "text", required: true, max: 100},
      {name: "resolved_at", type: "text", max: 100},
      {name: "occurrences", type: "number", required: true, min: 1, onlyInt: true},
      {name: "evidence", type: "json", required: true},
    ],
    indexes: [
      'CREATE UNIQUE INDEX idx_quality_alert_key ON quality_alerts(alert_key)',
      'CREATE INDEX idx_quality_alert_scope ON quality_alerts(scope_key,status)',
      'CREATE INDEX idx_quality_alert_history ON quality_alerts(astronaut_id,last_checked_at DESC)',
    ],
  }));
}, (app) => {
  // We remove only monitoring collections when this migration is rolled back.
  app.delete(app.findCollectionByNameOrId("quality_alerts"));
  app.delete(app.findCollectionByNameOrId("quality_checks"));
});
