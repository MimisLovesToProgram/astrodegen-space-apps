/// <reference path="../pb_data/types.d.ts" />
// Step 3 support: give sensor readings a real capture timestamp, mission
// day, and unit so the assessment engine can rebuild daily series, and give
// astronauts a stable crew identifier for generator crew_id mapping.
migrate((app) => {
  const astronauts = app.findCollectionByNameOrId("pbc_897795290");
  astronauts.fields.add(new TextField({
    name: "crew_id",
    required: false,
  }));
  app.save(astronauts);

  const readings = app.findCollectionByNameOrId("pbc_3796695146");
  readings.fields.add(new DateField({
    name: "captured_at",
    required: false,
  }));
  readings.fields.add(new NumberField({
    name: "mission_day",
    required: false,
  }));
  readings.fields.add(new TextField({
    name: "unit",
    required: false,
  }));
  app.save(readings);
}, (app) => {
  const astronauts = app.findCollectionByNameOrId("pbc_897795290");
  const crewField = astronauts.fields.getByName("crew_id");
  if (crewField) {
    astronauts.fields.removeById(crewField.id);
    app.save(astronauts);
  }

  const readings = app.findCollectionByNameOrId("pbc_3796695146");
  for (const name of ["captured_at", "mission_day", "unit"]) {
    const field = readings.fields.getByName(name);
    if (field) {
      readings.fields.removeById(field.id);
    }
  }
  app.save(readings);
})
