/// <reference path="../pb_data/types.d.ts" />
// We define storage for assessment results; we do not calculate risks here.
migrate((app) => {
  const collection = new Collection({
    // We leave access restricted to superusers through the built-in record APIs.
    "createRule": null,
    "deleteRule": null,
    "fields": [
      {
        "autogeneratePattern": "[a-z0-9]{15}",
        "help": "",
        "hidden": false,
        "id": "text3208210256",
        "max": 15,
        "min": 15,
        "name": "id",
        "pattern": "^[a-z0-9]+$",
        "presentable": false,
        "primaryKey": true,
        "required": true,
        "system": true,
        "type": "text"
      },
      {
        "cascadeDelete": false,
        "collectionId": "pbc_897795290",
        "help": "",
        "hidden": false,
        "id": "relation1571665637",
        "maxSelect": 0,
        "minSelect": 0,
        "name": "astronaut",
        // We leave the astronaut link optional in this collection definition.
        "presentable": false,
        "required": false,
        "system": false,
        "type": "relation"
      },
      {
        "help": "",
        "hidden": false,
        "id": "select2812878347",
        "maxSelect": 0,
        "name": "domain",
        // We identify which health domain the stored assessment describes.
        "presentable": false,
        "required": true,
        "system": false,
        "type": "select",
        "values": [
          "immune",
          "cardiovascular",
          "behavioral",
          "bone_loss"
        ]
      },
      {
        "help": "",
        "hidden": false,
        "id": "select342059477",
        "maxSelect": 0,
        "name": "domain_status",
        // We store one of the listed status labels without deriving it here.
        "presentable": false,
        "required": true,
        "system": false,
        "type": "select",
        "values": [
          "green",
          "yellow",
          "orange",
          "red"
        ]
      },
      {
        "help": "",
        "hidden": false,
        "id": "number1140588078",
        "max": 100,
        "min": 0,
        "name": "risk_score",
        // We constrain the stored score to 0–100 while allowing decimal values.
        "onlyInt": false,
        "presentable": false,
        "required": true,
        "system": false,
        "type": "number"
      },
      {
        "help": "",
        "hidden": false,
        "id": "json1915095946",
        "maxSize": 0,
        "name": "details",
        // We keep optional explanations or supporting data in a JSON field.
        "presentable": false,
        "required": false,
        "system": false,
        "type": "json"
      },
      {
        "hidden": false,
        "id": "autodate2990389176",
        "name": "created",
        "onCreate": true,
        "onUpdate": false,
        "presentable": false,
        "system": false,
        "type": "autodate"
      },
      {
        "hidden": false,
        "id": "autodate1330134206",
        "name": "assessed_at",
        // We refresh this time on every update, so we do not preserve an
        // immutable original assessment time in this field.
        "onCreate": true,
        "onUpdate": true,
        "presentable": false,
        "system": false,
        "type": "autodate"
      }
    ],
    "id": "pbc_670447587",
    "indexes": [],
    "listRule": null,
    "name": "domain_assessments",
    "system": false,
    "type": "base",
    "updateRule": null,
    "viewRule": null
  });

  return app.save(collection);
}, (app) => {
  // We remove the results collection if we roll back this migration.
  const collection = app.findCollectionByNameOrId("pbc_670447587");

  return app.delete(collection);
})
