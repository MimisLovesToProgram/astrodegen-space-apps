/// <reference path="../pb_data/types.d.ts" />
// The first Step 3 migration's astronauts change did not persist; add the
// stable crew identifier on its own so generator crew_ids map to records.
migrate((app) => {
  const astronauts = app.findCollectionByNameOrId("pbc_897795290");
  if (!astronauts.fields.getByName("crew_id")) {
    astronauts.fields.add(new TextField({
      name: "crew_id",
      required: false,
    }));
    app.save(astronauts);
  }
}, (app) => {
  const astronauts = app.findCollectionByNameOrId("pbc_897795290");
  const field = astronauts.fields.getByName("crew_id");
  if (field) {
    astronauts.fields.removeById(field.id);
    app.save(astronauts);
  }
})
