// These routes deliberately use transactions for idempotent capture and
// validation completion. Built-in APIs provide authenticated lists and reads.
routerAdd("POST", "/api/astrocrates/capture", (e) => {
  if (!["ingest", "worker"].includes(e.auth.getString("role"))) {
    throw new ForbiddenError("Capture requires an ingest or worker service");
  }
  const body = e.requestInfo().body;
  if (typeof body.delivery_key !== "string" || !body.delivery_key ||
      typeof body.payload !== "string" || typeof body.assume_utc !== "boolean" ||
      !["json", "python_repr"].includes(body.payload_encoding)) {
    throw new BadRequestError("Invalid capture envelope");
  }
  if (body.validation_time && (typeof body.validation_time !== "string" ||
      !/^\d{4}-\d\d-\d\dT.*(?:Z|[+-]\d\d:\d\d)$/.test(body.validation_time) ||
      !Number.isFinite(Date.parse(body.validation_time)))) {
    throw new BadRequestError("Replay validation_time must be an aware timestamp");
  }
  let output;
  $app.runInTransaction((tx) => {
    const existing = tx.findRecordsByFilter("sensor_packets",
      "producer = {:producer} && delivery_key = {:key}", "", 1, 0,
      {producer: e.auth.id, key: body.delivery_key});
    if (existing.length) {
      const record = existing[0];
      if (record.getString("payload") !== body.payload ||
          record.getString("payload_encoding") !== body.payload_encoding ||
          record.getBool("assume_utc") !== body.assume_utc ||
          record.getString("validation_time") !== (body.validation_time || "")) {
        throw new BadRequestError("Delivery key was already used for different content");
      }
      output = {id: record.id, status: record.getString("status"), replay: true};
      return;
    }
    const record = new Record(tx.findCollectionByNameOrId("sensor_packets"));
    record.load({delivery_key: body.delivery_key, producer: e.auth.id,
      payload: body.payload, payload_encoding: body.payload_encoding,
      assume_utc: body.assume_utc, validation_time: body.validation_time || "",
      captured_at: typeof body.captured_at === "string" ? body.captured_at : "",
      source: "synthetic_biosensors", status: "pending"});
    tx.save(record);
    output = {id: record.id, status: "pending", replay: false};
  });
  return e.json(200, output);
}, $apis.requireAuth("telemetry_services"));

// Aggregate in the database so monitoring does not download every packet.
// These counters cover the whole database; crew freshness is calculated from
// that crew member's validated history by the Python reporting command.
routerAdd("GET", "/api/astrocrates/quality-summary", (e) => {
  if (e.auth.getString("role") !== "worker") {
    throw new ForbiddenError("Quality summaries require a worker service");
  }
  const results = arrayOf(new DynamicModel({source: "", status: "", total: 0}));
  $app.db().newQuery(`SELECT p.source AS source, r.status AS status, COUNT(*) AS total
    FROM validation_results r JOIN sensor_packets p ON p.id=r.packet
    GROUP BY p.source, r.status`).all(results);
  const packets = new DynamicModel({pending: 0, processed: 0});
  $app.db().newQuery(`SELECT
    COUNT(CASE WHEN status='pending' THEN 1 END) AS pending,
    COUNT(CASE WHEN status='processed' THEN 1 END) AS processed FROM sensor_packets`).one(packets);
  return e.json(200, {scope: "all_database", packets: packets, results: results});
}, $apis.requireAuth("telemetry_services"));

routerAdd("POST", "/api/astrocrates/commit", (e) => {
  if (e.auth.getString("role") !== "worker") {
    throw new ForbiddenError("Validation requires a worker service");
  }
  const body = e.requestInfo().body;
  if (!Array.isArray(body.results) || body.results.length < 1 || body.results.length > 12) {
    throw new BadRequestError("Expected one packet's validation results");
  }
  const ingestion = {accepted: [], quarantined: [], duplicates: [], conflicts: []};
  let alreadyProcessed = false;
  $app.runInTransaction((tx) => {
    const packet = tx.findRecordById("sensor_packets", body.packet_id);
    if (packet.getString("status") === "processed") {
      alreadyProcessed = true;
      return;
    }
    for (const result of body.results) {
      if (!["accepted", "quarantined"].includes(result.status) || !Array.isArray(result.errors)) {
        throw new BadRequestError("Invalid validation result");
      }
      let status = result.status;
      let errors = result.errors;
      const obs = result.observation;
      if (status === "accepted") {
        if (!obs || !obs.astronaut_id || !obs.metric || !obs.captured_at || !obs.source ||
            typeof result.identity_key !== "string" || !result.identity_key ||
            typeof result.content_key !== "string" || !result.content_key) {
          throw new BadRequestError("Missing normalized observation");
        }
        const existing = tx.findRecordsByFilter("validated_observations",
          "identity_key = {:key}", "", 1, 0, {key: result.identity_key});
        if (existing.length) {
          status = existing[0].getString("content_key") === result.content_key ? "duplicate" : "conflict";
          if (status === "conflict") errors = ["A different measurement already exists at this identity"];
        } else {
          const clean = new Record(tx.findCollectionByNameOrId("validated_observations"));
          clean.load({packet: packet.id, identity_key: result.identity_key, content_key: result.content_key,
            astronaut_id: obs.astronaut_id, metric: obs.metric, captured_at: obs.captured_at, observation: obs});
          tx.save(clean);
        }
      }
      const audit = new Record(tx.findCollectionByNameOrId("validation_results"));
      audit.load({packet: packet.id, metric: obs ? obs.metric : "", status: status, errors: errors});
      tx.save(audit);
      if (status === "accepted") ingestion.accepted.push(obs);
      else {
        const bucket = {quarantined: "quarantined", duplicate: "duplicates", conflict: "conflicts"}[status];
        ingestion[bucket].push({raw_id: audit.id, errors: errors, observation: obs});
      }
    }
    const counts = {};
    for (const key of Object.keys(ingestion)) counts[key] = ingestion[key].length;
    packet.set("status", "processed");
    packet.set("processed_at", new Date().toISOString());
    packet.set("counts", counts);
    tx.save(packet);
  });
  return e.json(200, {packet_id: body.packet_id, already_processed: alreadyProcessed, ingestion: ingestion});
}, $apis.requireAuth("telemetry_services"));
