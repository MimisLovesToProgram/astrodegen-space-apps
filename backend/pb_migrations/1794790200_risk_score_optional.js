/// <reference path="../pb_data/types.d.ts" />
// PocketBase treats 0 as blank for required number fields; a green domain
// legitimately scores 0, so the requirement is relaxed to optional.
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_670447587");
  const field = collection.fields.getByName("risk_score");
  if (field && field.required) {
    field.required = false;
    app.save(collection);
  }
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_670447587");
  const field = collection.fields.getByName("risk_score");
  if (field && !field.required) {
    field.required = true;
    app.save(collection);
  }
})
