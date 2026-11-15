// We reduce the complete history to the latest reading per UTC day/metric
// inside SQLite, so we do not impose a hidden 250-record history cutoff.
module.exports.response = (e, crew, id) => {
  const readings = arrayOf(new DynamicModel({observation_json: "", metric: "", captured_at: "", source: ""}));
  e.app.db().newQuery(`SELECT observation_json,metric,captured_at,source FROM (
    SELECT CAST(observation AS TEXT) AS observation_json,metric,captured_at,
      COALESCE(json_extract(observation,'$.source'),'') AS source,
      ROW_NUMBER() OVER(PARTITION BY substr(captured_at,1,10),metric
        ORDER BY captured_at DESC,json_extract(observation,'$.source') ASC,id DESC) AS position
    FROM validated_observations WHERE astronaut_id={:crew} OR astronaut_id={:record}
  ) WHERE position=1 ORDER BY captured_at,metric`).bind({crew: id, record: crew.id}).all(readings);
  const runs = arrayOf(new DynamicModel({result_json: "", assessed_at: ""}));
  const policyId = $os.getenv("ASTROCRATES_POLICY_ID");
  const policyFilter = policyId ? " AND policy_id={:policy}" : "";
  e.app.db().newQuery(`SELECT result_json,assessed_at FROM (
    SELECT CAST(result AS TEXT) AS result_json,assessed_at,
      ROW_NUMBER() OVER(PARTITION BY substr(assessed_at,1,10)
        ORDER BY assessed_at DESC,created_at DESC,rowid DESC) AS position
    FROM assessment_runs WHERE (astronaut_id={:crew} OR astronaut_id={:record})` + policyFilter +
    `) WHERE position=1 ORDER BY assessed_at`).bind({crew: id, record: crew.id, policy: policyId}).all(runs);
  const dailyAssessments = {};
  for (const run of runs) dailyAssessments[run.assessed_at.slice(0, 10)] = JSON.parse(run.result_json);
  // We keep the field aliases requested by the frontend, while the database
  // and assessment engine continue using the canonical ingestion names.
  const aliases = {hrv_rmssd: "hrv", sleep_quality: "sleep_q", social_interaction: "social_interactions"};
  const output = {};
  const modes = {};
  let unknown = 0;
  let known = 0;
  for (const reading of readings) {
    const observation = JSON.parse(reading.observation_json);
    const day = reading.captured_at.slice(0, 10);
    if (!output[day]) output[day] = {};
    const assessment = dailyAssessments[day];
    const assessed = assessment && assessment.metrics ? assessment.metrics[reading.metric] : null;
    let level = null;
    // We attach a warning only to the exact reading that was assessed. A newer
    // reading on the same day does not inherit an old or unrelated green flag.
    if (assessed && assessed.captured_at === reading.captured_at && assessed.source === reading.source &&
        Number.isInteger(assessed.level) && assessed.level >= 0 && assessed.level <= 3) {
      level = assessed.level;
    }
    if (assessment) modes[assessment.policy_purpose || "unknown"] = true;
    if (level === null) unknown++;
    else known++;
    output[day][aliases[reading.metric] || reading.metric] = [observation.value, level];
  }
  e.response.header().set("Cache-Control", "no-store");
  e.response.header().set("X-Crew-Id", id);
  e.response.header().set("X-Assessment-Status", !readings.length ? "no_data" : !known ? "pending" : unknown ? "partial" : "complete");
  e.response.header().set("X-Assessment-Mode", Object.keys(modes).sort().join(",") || "unassessed");
  e.response.header().set("X-Unknown-Metrics", String(unknown));
  return e.json(200, output);
};
