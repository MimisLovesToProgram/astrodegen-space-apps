// We use short database transactions for claiming work, and run the Python
// calculations outside those transactions so ingestion can keep writing.
function guard(e) {
  if (e.auth.getString("role") !== "worker") throw new ForbiddenError("Assessment jobs require a worker service");
}

function exportJob(job) {
  return {id: job.id, astronaut_id: job.getString("astronaut_id"), as_of: job.getString("as_of"),
    claim_token: job.getString("claim_token"), policy: JSON.parse(job.getString("policy")),
    observations: JSON.parse(job.getString("observations") || "[]"),
    history_may_be_truncated: job.getBool("history_may_be_truncated")};
}

module.exports.enqueue = (e) => {
  guard(e);
  const body = e.requestInfo().body;
  if (!/^[a-f0-9]{64}$/.test(body.job_key || "") || !/^[a-f0-9]{64}$/.test(body.policy_digest || "") ||
      typeof body.astronaut_id !== "string" || !body.astronaut_id || !body.policy ||
      !Array.isArray(body.observations) || body.observations.length > 10000 ||
      typeof body.as_of !== "string" || !Number.isFinite(Date.parse(body.as_of))) {
    throw new BadRequestError("Invalid assessment job");
  }
  let result;
  $app.runInTransaction((tx) => {
    const existing = tx.findRecordsByFilter("assessment_jobs", "job_key={:key}", "", 1, 0, {key: body.job_key});
    if (existing.length) {
      result = {id: existing[0].id, status: existing[0].getString("status"), duplicate: true};
      return;
    }
    const job = new Record(tx.findCollectionByNameOrId("assessment_jobs"));
    job.load({job_key: body.job_key, astronaut_id: body.astronaut_id, policy_id: body.policy.policy_id,
      policy_digest: body.policy_digest, as_of: body.as_of, policy: body.policy,
      observations: body.observations, history_may_be_truncated: !!body.history_may_be_truncated,
      status: "pending", attempts: 0});
    tx.save(job);
    result = {id: job.id, status: "pending", duplicate: false};
  });
  return e.json(200, result);
};

module.exports.claim = (e) => {
  guard(e);
  const body = e.requestInfo().body;
  const seconds = body.lease_seconds === undefined ? 30 : body.lease_seconds;
  if (!Number.isInteger(seconds) || seconds < 1 || seconds > 300) throw new BadRequestError("Invalid lease duration");
  let result = null;
  $app.runInTransaction((tx) => {
    const now = new Date().toISOString();
    const params = {now: now};
    const scope = body.job_id ? " && id={:job}" : "";
    if (body.job_id) params.job = body.job_id;
    // We reclaim expired work, but cap automatic attempts to avoid endless
    // loops on a broken policy. Manual retry remains a separate operation.
    const exhausted = tx.findRecordsByFilter("assessment_jobs",
      "status='running' && lease_until < {:now} && attempts >= 3" + scope, "", 100, 0, params);
    for (const job of exhausted) {
      job.load({status: "failed", claim_token: "", error: "Lease expired after retry limit"});
      tx.save(job);
    }
    const candidates = tx.findRecordsByFilter("assessment_jobs",
      "attempts < 3 && (status='pending' || (status='running' && lease_until < {:now}))" + scope,
      "as_of,created_at,id", 1, 0, params);
    if (!candidates.length) return;
    const job = candidates[0];
    job.load({status: "running", claim_token: $security.randomString(32),
      lease_until: new Date(Date.now() + seconds * 1000).toISOString(),
      attempts: job.getInt("attempts") + 1, error: ""});
    tx.save(job);
    result = exportJob(job);
  });
  return e.json(200, {job: result});
};

module.exports.fail = (e) => {
  guard(e);
  const body = e.requestInfo().body;
  $app.runInTransaction((tx) => {
    const job = tx.findRecordById("assessment_jobs", body.job_id);
    if (job.getString("status") !== "running" || job.getString("claim_token") !== body.claim_token) {
      throw new ApiError(409, "This worker no longer owns the job");
    }
    job.load({status: "failed", claim_token: "", lease_until: "",
              error: typeof body.error === "string" ? body.error.slice(0, 5000) : "Assessment failed"});
    tx.save(job);
  });
  return e.json(200, {status: "failed"});
};

module.exports.retry = (e) => {
  guard(e);
  const body = e.requestInfo().body;
  $app.runInTransaction((tx) => {
    const job = tx.findRecordById("assessment_jobs", body.job_id);
    if (job.getString("status") !== "failed") throw new ApiError(409, "Only failed jobs can be retried");
    if (job.getInt("attempts") >= 3 && body.reset_attempts !== true) throw new ApiError(409, "Retry limit reached");
    job.load({status: "pending", error: "", claim_token: "", lease_until: ""});
    if (body.reset_attempts === true) job.set("attempts", 0);
    tx.save(job);
  });
  return e.json(200, {status: "pending"});
};
