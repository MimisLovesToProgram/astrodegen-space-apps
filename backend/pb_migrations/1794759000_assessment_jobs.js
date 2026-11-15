// We keep queued inputs, immutable assessment results, and escalation events
// in the same backend as the validated sensor history.
migrate((app) => {
  const worker = '@request.auth.collectionName = "telemetry_services" && @request.auth.role = "worker"';
  const reader = '@request.auth.collectionName = "telemetry_services" && (@request.auth.role = "worker" || @request.auth.role = "reader")';
  const jobs = new Collection({
    type: "base", name: "assessment_jobs", listRule: worker, viewRule: worker,
    createRule: null, updateRule: null, deleteRule: null,
    fields: [
      {name: "job_key", type: "text", required: true, max: 64},
      {name: "astronaut_id", type: "text", required: true, max: 200},
      {name: "policy_id", type: "text", required: true, max: 100},
      {name: "policy_digest", type: "text", required: true, max: 64},
      {name: "as_of", type: "text", required: true, max: 100},
      {name: "policy", type: "json", required: true},
      {name: "observations", type: "json"},
      {name: "history_may_be_truncated", type: "bool"},
      {name: "status", type: "select", required: true, maxSelect: 1, values: ["pending", "running", "complete", "failed"]},
      {name: "attempts", type: "number", min: 0, onlyInt: true},
      {name: "claim_token", type: "text", max: 100},
      {name: "lease_until", type: "text", max: 100},
      {name: "result_run_id", type: "text", max: 15},
      {name: "error", type: "text", max: 5000},
      {name: "created_at", type: "autodate", onCreate: true, onUpdate: false},
    ],
    indexes: ['CREATE UNIQUE INDEX idx_assessment_job_key ON assessment_jobs(job_key)',
              'CREATE INDEX idx_assessment_pending ON assessment_jobs(status,as_of)'],
  });
  app.save(jobs);
  const runs = new Collection({
    type: "base", name: "assessment_runs", listRule: reader, viewRule: reader,
    createRule: null, updateRule: null, deleteRule: null,
    fields: [
      {name: "assessment_key", type: "text", required: true, max: 64},
      {name: "job", type: "relation", required: true, maxSelect: 1, collectionId: jobs.id},
      {name: "astronaut_id", type: "text", required: true, max: 200},
      {name: "assessed_at", type: "text", required: true, max: 100},
      {name: "policy_id", type: "text", required: true, max: 100},
      {name: "policy_digest", type: "text", required: true, max: 64},
      {name: "result", type: "json", required: true},
      {name: "created_at", type: "autodate", onCreate: true, onUpdate: false},
    ],
    indexes: ['CREATE UNIQUE INDEX idx_assessment_result_key ON assessment_runs(assessment_key)',
              'CREATE INDEX idx_assessment_history ON assessment_runs(astronaut_id,assessed_at DESC)'],
  });
  app.save(runs);
  const astronauts = app.findCollectionByNameOrId("astronauts");
  astronauts.fields.add(new TextField({name: "crew_id", max: 200}));
  astronauts.addIndex("idx_astronaut_crew_id", true, "crew_id", "crew_id != ''");
  app.save(astronauts);
  const domains = app.findCollectionByNameOrId("domain_assessments");
  // We allow a genuine zero-point score. The commit route still requires an
  // explicit finite score whenever a domain has a known warning level.
  domains.fields.getByName("risk_score").required = false;
  domains.fields.add(new RelationField({name: "assessment_run", collectionId: runs.id, maxSelect: 1}));
  domains.fields.add(new TextField({name: "policy_digest", max: 64}));
  domains.fields.add(new TextField({name: "evaluated_at", max: 100}));
  domains.fields.add(new NumberField({name: "level", min: 0, max: 3, onlyInt: true}));
  domains.addIndex("idx_domain_run", true, "assessment_run,domain", "assessment_run != ''");
  app.save(domains);
  app.save(new Collection({
    type: "base", name: "escalation_events", listRule: reader, viewRule: reader,
    createRule: null, updateRule: null, deleteRule: null,
    fields: [
      {name: "event_key", type: "text", required: true, max: 64},
      {name: "assessment_run", type: "relation", required: true, maxSelect: 1, collectionId: runs.id},
      {name: "astronaut", type: "relation", required: true, maxSelect: 1, collectionId: astronauts.id},
      {name: "astronaut_id", type: "text", required: true, max: 200},
      {name: "domain", type: "text", required: true, max: 100},
      {name: "level", type: "number", required: true, min: 2, max: 3, onlyInt: true},
      {name: "occurred_at", type: "text", required: true, max: 100},
      {name: "payload", type: "json", required: true},
      {name: "delivery_status", type: "select", maxSelect: 1, required: true, values: ["pending", "acknowledged"]},
      {name: "created_at", type: "autodate", onCreate: true, onUpdate: false},
    ],
    indexes: ['CREATE UNIQUE INDEX idx_escalation_event_key ON escalation_events(event_key)',
              'CREATE INDEX idx_escalation_crew ON escalation_events(astronaut_id,occurred_at DESC)'],
  }));
});
