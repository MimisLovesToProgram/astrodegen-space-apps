// We share ownership checks between the profile and sensor-history routes.
function profile(e) {
  const id = e.auth.getString("astronaut");
  if (!id) throw new ForbiddenError("No crew profile is linked to this account");
  return e.app.findRecordById("astronauts", id);
}

function crewId(crew) {
  return crew.getString("crew_id") || crew.id;
}

module.exports.login = (e) => {
  e.response.header().set("Cache-Control", "no-store");
  const window = Math.floor(Date.now() / 60000);
  const clientKey = $security.sha256(e.realIP());
  let attempts = 0;
  e.app.runInTransaction((tx) => {
    tx.db().newQuery("DELETE FROM astrocrates_login_limits WHERE window < {:old}").bind({old: window - 2}).execute();
    tx.db().newQuery(`INSERT INTO astrocrates_login_limits(client_key,window,attempts) VALUES ({:client},{:window},1)
      ON CONFLICT(client_key) DO UPDATE SET window=excluded.window,
      attempts=CASE WHEN astrocrates_login_limits.window=excluded.window THEN attempts+1 ELSE 1 END`)
      .bind({client: clientKey, window: window}).execute();
    const count = new DynamicModel({attempts: 0});
    tx.db().newQuery("SELECT attempts FROM astrocrates_login_limits WHERE client_key={:client}")
      .bind({client: clientKey}).one(count);
    attempts = count.attempts;
  });
  if (attempts > 100) {
    e.response.header().set("Retry-After", String(60 - Math.floor(Date.now() / 1000) % 60));
    throw new ApiError(429, "Too many login attempts; try again shortly");
  }
  const body = e.requestInfo().body;
  const failed = {crewId: ""};
  if (typeof body.username !== "string" || typeof body.password !== "string" ||
      !body.username.trim() || !body.password || body.username.length > 254 || body.password.length > 4096) {
    return e.json(200, failed);
  }
  const users = e.app.findCollectionByNameOrId("users");
  // We refuse this password-only adapter if MFA is enabled, rather than issue
  // a token that bypasses the configured account authentication policy.
  if (!users.passwordAuth.enabled || users.authRule === null || users.mfa.enabled) return e.json(200, failed);
  const username = body.username.trim();
  const field = username.includes("@") ? "email" : "username";
  const records = e.app.findRecordsByFilter("users", field + "={:identity}", "", 1, 0, {identity: username});
  if (!records.length || !records[0].validatePassword(body.password)) return e.json(200, failed);
  const user = records[0];
  if (!e.app.canAccessRecord(user, e.requestInfo(), users.authRule) || !user.getString("astronaut")) {
    return e.json(200, failed);
  }
  const crew = e.app.findRecordById("astronauts", user.getString("astronaut"));
  // We return a real PocketBase token; knowing a crew ID alone is not enough
  // to read that person's records.
  return e.json(200, {crewId: crewId(crew), token: user.newAuthToken()});
};

module.exports.me = (e) => {
  const crew = profile(e);
  e.response.header().set("Cache-Control", "no-store");
  return e.json(200, {crewId: crewId(crew), name: crew.getString("name"), status: crew.getString("status")});
};

module.exports.sensors = (e) => {
  const crew = profile(e);
  const id = crewId(crew);
  const requested = e.requestInfo().body.crewId;
  if (typeof requested !== "string" || !requested) throw new BadRequestError("crewId is required");
  if (requested !== id && requested !== crew.id) throw new ForbiddenError("This account cannot read another crew member");
  return require(__hooks + "/crew_history.js").response(e, crew, id);
};
