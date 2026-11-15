// We keep the public login adapter separate from token-protected crew routes.
routerAdd("POST", "/api/astrocrates/login", (e) => {
  return require(__hooks + "/crew_api.js").login(e);
});
routerAdd("POST", "/api/astrocrates/sensors", (e) => {
  return require(__hooks + "/crew_api.js").sensors(e);
}, $apis.requireAuth("users"));
routerAdd("GET", "/api/astrocrates/me", (e) => {
  return require(__hooks + "/crew_api.js").me(e);
}, $apis.requireAuth("users"));
routerAdd("POST", "/api/astrocrates/checkin", (e) => {
  return require(__hooks + "/crew_checkin.js").save(e);
}, $apis.requireAuth("users"));
