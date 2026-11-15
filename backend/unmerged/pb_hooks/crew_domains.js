// We return the four domain results from the crew member's latest assessment.
// Scores are configured risk points from 0 to 100, where higher is worse.
// They are not health percentages or probabilities.
const DOMAINS = ["cardiovascular", "immune", "behavioral", "bone_loss"];

module.exports.response = (e, crew, id) => {
  const runs = arrayOf(new DynamicModel({result_json: ""}));
  const policyId = $os.getenv("ASTROCRATES_POLICY_ID");
  const policyFilter = policyId ? " AND policy_id={:policy}" : "";
  // We use the same ordering as the daily history, so both routes agree on
  // which assessment is the latest one.
  e.app.db().newQuery(`SELECT CAST(result AS TEXT) AS result_json FROM assessment_runs
    WHERE (astronaut_id={:crew} OR astronaut_id={:record})` + policyFilter + `
    ORDER BY assessed_at DESC,created_at DESC,rowid DESC LIMIT 1`)
    .bind({crew: id, record: crew.id, policy: policyId}).all(runs);
  e.response.header().set("Cache-Control", "no-store");
  if (!runs.length) return e.json(200, {assessedAt: null, mode: "unassessed", domains: {}});
  const result = JSON.parse(runs[0].result_json);
  const domains = {};
  for (const name of DOMAINS) {
    const domain = result.domains ? result.domains[name] : null;
    const valid = domain && Number.isInteger(domain.level) && domain.level >= 0 && domain.level <= 3 &&
      typeof domain.risk_score === "number" && Number.isFinite(domain.risk_score);
    // We keep an unknown domain as null rather than reporting a zero score,
    // which the app would otherwise read as a healthy result.
    domains[name] = {
      score: valid ? domain.risk_score : null,
      level: valid ? domain.level : null,
      complete: !!domain && domain.data_status === "complete",
      lowerBound: !!domain && domain.score_is_lower_bound === true,
    };
  }
  return e.json(200, {assessedAt: result.assessed_at, mode: result.policy_purpose || "unknown", domains: domains});
};
