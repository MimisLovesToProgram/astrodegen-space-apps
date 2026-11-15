/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_2428134213")

  // update collection data
  unmarshal({
    "name": "domain_assessments"
  }, collection)

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_2428134213")

  // update collection data
  unmarshal({
    "name": "domain"
  }, collection)

  return app.save(collection)
})
