/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_897795290")

  // update collection data
  unmarshal({
    "name": "astronautsOLD"
  }, collection)

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_897795290")

  // update collection data
  unmarshal({
    "name": "astronauts"
  }, collection)

  return app.save(collection)
})
