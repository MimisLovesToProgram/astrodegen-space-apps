// Raw capture, per-metric outcomes, and clean history. Service users are
// provisioned by an administrator; there is no public account registration.
migrate((app) => {
  const services = new Collection({
    type: "auth", name: "telemetry_services",
    listRule: "id = @request.auth.id", viewRule: "id = @request.auth.id",
    createRule: null, updateRule: null, deleteRule: null,
    fields: [{name: "role", type: "select", required: true, maxSelect: 1,
              values: ["ingest", "worker", "reader"]}],
  });
  app.save(services);
  const worker = '@request.auth.collectionName = "telemetry_services" && @request.auth.role = "worker"';
  const reader = '@request.auth.collectionName = "telemetry_services" && (@request.auth.role = "worker" || @request.auth.role = "reader")';
  const packets = new Collection({
    type: "base", name: "sensor_packets", listRule: worker, viewRule: worker,
    createRule: null, updateRule: null, deleteRule: null,
    fields: [
      {name: "delivery_key", type: "text", required: true, max: 100},
      {name: "producer", type: "relation", collectionId: services.id, maxSelect: 1, required: true},
      {name: "received_at", type: "autodate", onCreate: true, onUpdate: false},
      {name: "captured_at", type: "text", max: 200},
      {name: "source", type: "text", required: true, max: 100},
      {name: "payload", type: "text", required: true, max: 2097152},
      {name: "payload_encoding", type: "select", required: true, maxSelect: 1, values: ["json", "python_repr"]},
      {name: "assume_utc", type: "bool"},
      {name: "validation_time", type: "text", max: 100},
      {name: "status", type: "select", required: true, maxSelect: 1, values: ["pending", "processed"]},
      {name: "processed_at", type: "date"},
      {name: "counts", type: "json"},
    ],
    indexes: [
      'CREATE UNIQUE INDEX idx_packet_delivery ON sensor_packets (producer, delivery_key)',
      'CREATE INDEX idx_packet_pending ON sensor_packets (status, received_at, id)',
    ],
  });
  app.save(packets);
  app.save(new Collection({
    type: "base", name: "validation_results", listRule: worker, viewRule: worker,
    createRule: null, updateRule: null, deleteRule: null,
    fields: [
      {name: "packet", type: "relation", collectionId: packets.id, required: true, maxSelect: 1},
      {name: "metric", type: "text", max: 100},
      {name: "status", type: "select", required: true, maxSelect: 1,
       values: ["accepted", "quarantined", "duplicate", "conflict"]},
      {name: "errors", type: "json"},
    ],
    indexes: ['CREATE INDEX idx_result_packet ON validation_results (packet)'],
  }));
  app.save(new Collection({
    type: "base", name: "validated_observations", listRule: reader, viewRule: reader,
    createRule: null, updateRule: null, deleteRule: null,
    fields: [
      {name: "packet", type: "relation", collectionId: packets.id, required: true, maxSelect: 1},
      {name: "identity_key", type: "text", required: true, max: 5000},
      {name: "content_key", type: "text", required: true, max: 2097152},
      {name: "astronaut_id", type: "text", required: true, max: 200},
      {name: "metric", type: "text", required: true, max: 100},
      {name: "captured_at", type: "text", required: true, max: 100},
      {name: "observation", type: "json", required: true},
    ],
    indexes: [
      'CREATE UNIQUE INDEX idx_observation_identity ON validated_observations (identity_key)',
      'CREATE INDEX idx_observation_history ON validated_observations (astronaut_id, captured_at DESC)',
    ],
  }));
}, (app) => {
  for (const name of ["validated_observations", "validation_results", "sensor_packets", "telemetry_services"]) {
    app.delete(app.findCollectionByNameOrId(name));
  }
});
