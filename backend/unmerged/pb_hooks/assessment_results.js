// We commit a result, its domain rows, events, and job completion together.
module.exports.complete = (e) => {
  if (e.auth.getString("role") !== "worker") throw new ForbiddenError("Assessment results require a worker service");
  const body = e.requestInfo().body;
  const result = body.result;
  const names = ["cardiovascular", "immune", "behavioral", "bone_loss"];
  const colors = ["green", "yellow", "orange", "red"];
  if (!result || result.schema_version !== "astrocrates.assessment.v1" ||
      !/^[a-f0-9]{64}$/.test(result.assessment_key || "") || !result.domains) {
    throw new BadRequestError("Invalid assessment result");
  }
  for (const name of names) {
    const domain = result.domains[name];
    if (!domain || (domain.level === null ? (domain.status !== "unknown" || domain.risk_score !== null) :
        (!Number.isInteger(domain.level) || domain.level < 0 || domain.level > 3 ||
         domain.status !== colors[domain.level] || typeof domain.risk_score !== "number" ||
         !Number.isFinite(domain.risk_score) || domain.risk_score < 0 || domain.risk_score > 100))) {
      throw new BadRequestError("Invalid domain result");
    }
  }
  let output;
  $app.runInTransaction((tx) => {
    const job = tx.findRecordById("assessment_jobs", body.job_id);
    if (job.getString("status") === "complete") {
      output = {run_id: job.getString("result_run_id"), duplicate: true, events: 0};
      return;
    }
    if (job.getString("status") !== "running" || job.getString("claim_token") !== body.claim_token ||
        job.getString("lease_until") < new Date().toISOString()) {
      throw new ApiError(409, "This worker no longer owns a live job lease");
    }
    if (result.astronaut_id !== job.getString("astronaut_id") || result.assessed_at !== job.getString("as_of") ||
        result.policy_digest !== job.getString("policy_digest") || result.policy_id !== job.getString("policy_id")) {
      throw new BadRequestError("Result does not match the claimed input snapshot");
    }
    const existing = tx.findRecordsByFilter("assessment_runs", "assessment_key={:key}", "", 1, 0,
                                           {key: result.assessment_key});
    if (existing.length) {
      job.load({status: "complete", result_run_id: existing[0].id, claim_token: "", lease_until: ""});
      tx.save(job);
      output = {run_id: existing[0].id, duplicate: true, events: 0};
      return;
    }
    // We compare every policy before updating the shared crew profile.
    // Historical results from a new policy must not rewind current status.
    const priorRuns = tx.findRecordsByFilter("assessment_runs",
      "astronaut_id={:crew}", "-assessed_at,-created_at,-id", 1, 0,
      {crew: result.astronaut_id});
    const advancesCurrent = !priorRuns.length || priorRuns[0].getString("assessed_at") <= result.assessed_at;
    const crewMatches = tx.findRecordsByFilter("astronauts", "crew_id={:crew} || id={:crew}", "", 1, 0,
                                              {crew: result.astronaut_id});
    const crew = crewMatches.length ? crewMatches[0] : new Record(tx.findCollectionByNameOrId("astronauts"));
    if (!crewMatches.length) crew.load({crew_id: result.astronaut_id, name: result.astronaut_id, status: "unknown"});
    if (advancesCurrent) crew.set("status", result.overall_status);
    tx.save(crew);
    const run = new Record(tx.findCollectionByNameOrId("assessment_runs"));
    run.load({assessment_key: result.assessment_key, job: job.id, astronaut_id: result.astronaut_id,
      assessed_at: result.assessed_at, policy_id: result.policy_id, policy_digest: result.policy_digest, result: result});
    tx.save(run);
    let events = 0;
    for (const name of names) {
      const domain = result.domains[name];
      // We keep unknown domains in the complete run JSON, without creating a
      // misleading zero-score/green row in the team's domain collection.
      if (domain.level === null) continue;
      const previous = tx.findRecordsByFilter("domain_assessments",
        "astronaut={:crew} && domain={:domain} && policy_digest={:policy} && evaluated_at <= {:at}",
        "-evaluated_at,-created,-id", 1, 0,
        {crew: crew.id, domain: name, policy: result.policy_digest, at: result.assessed_at});
      const previousLevel = previous.length ? previous[0].getInt("level") : null;
      const record = new Record(tx.findCollectionByNameOrId("domain_assessments"));
      record.load({astronaut: crew.id, domain: name, domain_status: domain.status, risk_score: domain.risk_score,
        details: domain, assessment_run: run.id, policy_digest: result.policy_digest,
        evaluated_at: result.assessed_at, level: domain.level});
      tx.save(record);
      if (advancesCurrent && domain.level >= 2 && (previousLevel === null || domain.level > previousLevel)) {
        // We emit only a new orange/red transition, not every repeated warning
        // or an older historical result that arrives after a newer assessment.
        const event = new Record(tx.findCollectionByNameOrId("escalation_events"));
        event.load({event_key: $security.sha256(result.assessment_key + ":" + name + ":" + domain.level),
          assessment_run: run.id, astronaut: crew.id, domain: name, level: domain.level,
          astronaut_id: result.astronaut_id,
          occurred_at: result.assessed_at, delivery_status: "pending",
          payload: {type: "escalation", crewId: result.astronaut_id, domain: name,
            level: domain.level, previous_level: previousLevel, policy_id: result.policy_id,
            policy_purpose: result.policy_purpose, assessed_at: result.assessed_at}});
        tx.save(event);
        events++;
      }
    }
    job.load({status: "complete", result_run_id: run.id, claim_token: "", lease_until: "", error: ""});
    tx.save(job);
    output = {run_id: run.id, duplicate: false, events: events};
  });
  return e.json(200, output);
};
