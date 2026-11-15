/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_2341825278")

  // update collection data
  unmarshal({
    "name": "sensor_readings"
  }, collection)

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_2341825278")

  // update collection data
  unmarshal({
    "name": "sensor"
  }, collection)

  return app.save(collection)
})
