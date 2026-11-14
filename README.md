# Astrocrates

An astronaut health-monitoring prototype by ASTRODEGEN for Space Apps preparation. Synthetic sensor packets are captured before validation, stored in SQLite, and exposed as clean history for assessment. The Flutter interface is an existing prototype. Health-risk calculations are still pending.

## Project layout

```text
frontend/                Existing Flutter app, assets, and platform projects
src/
  biosensors.py          Existing synthetic sensor scenarios
  ingest_validate/       Capture, validation, storage, worker, and assessment hook
tests/                   Python behavior and integration tests
docs/                    Architecture, decisions, team workflow, and task schedule
```

Keep features inside these folders rather than adding empty folders for planned components. `data/` is generated locally and ignored by Git.

## Run the connected demo

From the repository root:

```bash
PYTHONPATH=src python3 -m ingest_validate.cli --sensor-demo
PYTHONPATH=src python3 -m ingest_validate.cli --latest a --limit 250
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

A fresh synthetic mission produces 21 raw packets and 252 accepted observations. A repeat records retransmissions and detects duplicate observations. The demo uses an explicit simulation clock for its future-dated story. All sensor examples are synthetic.

For the existing frontend, run Flutter commands from `frontend/`. No frontend source or application identifiers have been changed during the folder reorganization.

See the [pipeline contract](docs/pipeline.md), [non-UI task schedule](docs/task-plan.md), and [team workflow](docs/team-workflow.md). Data-quality bounds and the prototype are not clinically validated.
