// We derive crew identity from authentication and keep raw check-ins durable.
module.exports.save = (e) => {
  const body = e.requestInfo().body;
  const crew = e.app.findRecordById("astronauts", e.auth.getString("astronaut"));
  const crewId = crew.getString("crew_id") || crew.id;
  if (body.crewId !== crewId) throw new ForbiddenError("This account cannot submit another crew member's check-in");
  if (typeof body.deliveryKey !== "string" || !/^[a-zA-Z0-9-]{8,70}$/.test(body.deliveryKey)) {
    throw new BadRequestError("A stable deliveryKey is required");
  }
  const input = body.values;
  const fields = ["sleep_h", "sleep_quality", "mood", "symptoms", "exercise_logged", "social_interaction", "activity_pct_target"];
  if (!input || Array.isArray(input) || typeof input !== "object" || Object.keys(input).some(key => !fields.includes(key)) ||
      fields.some(key => !Object.prototype.hasOwnProperty.call(input, key))) throw new BadRequestError("Invalid check-in fields");
  for (const [key, max] of [["sleep_h",24],["sleep_quality",5],["mood",5],["activity_pct_target",500]]) {
    const value = input[key];
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > max ||
        (["mood","sleep_quality"].includes(key) && (!Number.isInteger(value) || value < 1))) {
      throw new BadRequestError("Invalid " + key);
    }
  }
  if (typeof input.exercise_logged !== "boolean" || typeof input.social_interaction !== "boolean" ||
      !Array.isArray(input.symptoms) || input.symptoms.length > 20 || input.symptoms.some(value =>
        typeof value !== "string" || !value.trim() || value.length > 100)) throw new BadRequestError("Invalid symptoms or boolean values");
  const values = {};
  for (const field of fields) values[field] = input[field];
  let output;
  e.app.runInTransaction(tx => {
    const key = e.auth.id + ":" + body.deliveryKey;
    const existing = tx.findRecordsByFilter("sensor_packets", "delivery_key={:key} && crew_user={:user}", "", 1, 0,
      {key: key, user: e.auth.id});
    if (existing.length) {
      const packet = JSON.parse(existing[0].getString("payload"));
      const previous = {};
      for (const field of fields) previous[field] = packet[field];
      if (JSON.stringify(previous) !== JSON.stringify(values)) throw new ApiError(409, "Delivery key already used with different answers");
      output = {id: existing[0].id, status: existing[0].getString("status"), replay: true};
      return;
    }
    const captured = new Date().toISOString();
    const record = new Record(tx.findCollectionByNameOrId("sensor_packets"));
    record.load({delivery_key: key, crew_user: e.auth.id, source: "crew_checkin", status: "pending",
      captured_at: captured, payload_encoding: "json", assume_utc: false,
      payload: JSON.stringify({crew_id: crewId, timestamp: captured, ...values})});
    tx.save(record);
    output = {id: record.id, status: "pending", replay: false};
  });
  e.response.header().set("Cache-Control", "no-store");
  return e.json(202, output);
};
