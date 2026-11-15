// We keep record mutations behind worker-only routes, while built-in record
// APIs provide read access to the assessment history for authorized readers.
routerAdd("POST", "/api/astrocrates/assessment-jobs", (e) => {
  return require(__hooks + "/assessment_jobs.js").enqueue(e);
}, $apis.requireAuth("telemetry_services"));
routerAdd("POST", "/api/astrocrates/assessment-jobs/claim", (e) => {
  return require(__hooks + "/assessment_jobs.js").claim(e);
}, $apis.requireAuth("telemetry_services"));
routerAdd("POST", "/api/astrocrates/assessment-jobs/fail", (e) => {
  return require(__hooks + "/assessment_jobs.js").fail(e);
}, $apis.requireAuth("telemetry_services"));
routerAdd("POST", "/api/astrocrates/assessment-jobs/retry", (e) => {
  return require(__hooks + "/assessment_jobs.js").retry(e);
}, $apis.requireAuth("telemetry_services"));
routerAdd("POST", "/api/astrocrates/assessment-jobs/complete", (e) => {
  return require(__hooks + "/assessment_results.js").complete(e);
}, $apis.requireAuth("telemetry_services"));
