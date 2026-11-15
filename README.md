# Astrocrates

> \[!WARNING]
> Pliz push to to `dev` branch NOT MAIN!!!!!!!!
> even better Branch off dev , add your feature in a feature branch `feature/<MyFeature>` and
> then merge back to dev... just so we dont have many conflicts




An astronaut health-monitoring prototype by ASTRODEGEN. Synthetic sensor data is saved, validated, and prepared for health assessment. Configurable demo assessments and crew APIs are implemented; team-approved scoring and Flutter integration remain pending.

## Structure

```text
src/
  app_frontend/   Flutter app
  assessment/     Configurable assessment engine
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

For the shared API backend, follow the [PocketBase setup](backend/README.md).

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

See the [pipeline guide](docs/pipeline.md), [sensor contract](docs/sensor-contract.md), [assessment guide](docs/assessment.md), [frontend API](docs/frontend-api.md), and [task schedule](docs/task-plan.md).
