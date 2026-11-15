// We link an ordinary app user to one crew profile. Service accounts stay in
// their own collection and cannot be used as a frontend crew login.
migrate((app) => {
  const users = app.findCollectionByNameOrId("users");
  const astronauts = app.findCollectionByNameOrId("astronauts");
  if (!users.fields.getByName("username")) {
    users.fields.add(new TextField({name: "username", max: 64, pattern: "^[a-zA-Z0-9_.-]{3,64}$"}));
  }
  users.addIndex("idx_crew_username", true, "username", "username != ''");
  users.fields.add(new RelationField({name: "astronaut", collectionId: astronauts.id, maxSelect: 1}));
  users.passwordAuth.enabled = true;
  users.passwordAuth.identityFields = ["email", "username"];
  users.createRule = null;
  const self = '@request.auth.collectionName = "users" && id = @request.auth.id';
  users.listRule = self;
  users.viewRule = self;
  // We allow normal self-service account updates without letting a user
  // switch the crew relation and gain access to another astronaut's history.
  users.updateRule = self + " && @request.body.astronaut:changed = false";
  users.deleteRule = self;
  app.save(users);
  const own = '@request.auth.collectionName = "users" && id = @request.auth.astronaut';
  const staff = '@request.auth.collectionName = "telemetry_services" && (@request.auth.role = "worker" || @request.auth.role = "reader")';
  astronauts.listRule = "(" + own + ") || (" + staff + ")";
  astronauts.viewRule = astronauts.listRule;
  app.save(astronauts);
  // We keep a route-local counter rather than enable global limits that could
  // unexpectedly throttle sensor ingestion or existing service-account auth.
  app.db().newQuery(`CREATE TABLE IF NOT EXISTS astrocrates_login_limits (
    client_key TEXT PRIMARY KEY, window INTEGER NOT NULL, attempts INTEGER NOT NULL
  )`).execute();
});
