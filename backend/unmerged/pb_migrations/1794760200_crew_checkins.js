// We retain self-reported inputs in the raw inbox before worker validation.
migrate((app) => {
  const packets = app.findCollectionByNameOrId("sensor_packets");
  packets.fields.getByName("producer").required = false;
  packets.fields.add(new RelationField({name: "crew_user", collectionId: app.findCollectionByNameOrId("users").id, maxSelect: 1}));
  app.save(packets);
});
