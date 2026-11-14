# Astrocrates

An astronaut health-monitoring prototype by ASTRODEGEN. Synthetic sensor data is saved, validated, and prepared for health assessment. The risk engine is still pending.

## Structure

```text
src/
  app_frontend/   Flutter app
  ingest_validate/ Data pipeline
  biosensors.py   Synthetic sensors
  astrocrates.py  Pipeline commands
backend/    PocketBase configuration and APIs
tests/      Python and backend tests
docs/       Architecture and task schedule
```

## Run locally

From the repository root, using Python's standard library and SQLite:

```bash
PYTHONPATH=src python3 -m astrocrates --backend sqlite capture --interval 0 --process
PYTHONPATH=src python3 -m astrocrates --backend sqlite history a
```

For the shared API backend, follow the [PocketBase setup](backend/pocketbase/README.md).

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

See the [pipeline guide](docs/pipeline.md) and [non-UI task schedule](docs/task-plan.md).
