# Astrocrates

An astronaut health-monitoring prototype by ASTRODEGEN. We capture and validate sensor data, run configurable assessments, and display crew history in Flutter. Scoring uses team prototype rules with provisional color bands.

Work on a feature branch and open a pull request to `dev`.

```text
src/
  app_frontend/     Flutter app and frontend tests
  assessment/       Rules, time windows, scoring, and jobs
  ingest_validate/  Capture, validation, storage, and monitoring
  biosensors.py     Synthetic sensors
  astrocrates.py    Pipeline commands
backend/            PocketBase hooks and migrations
config/             Explicit assessment policies
tests/              Python and PocketBase tests
docs/               Setup, contracts, and task board
```

For local setup and commands, see the [backend guide](backend/README.md) and [frontend guide](src/app_frontend/README.md).

```bash
POCKETBASE_TEST_BINARY="$PWD/backend/pocketbase" PYTHONPATH=src python3 -m unittest discover -s tests -v
```

See the [task board](docs/task-plan.md), [assessment guide](docs/assessment.md), and [API contract](docs/frontend-api.md).
