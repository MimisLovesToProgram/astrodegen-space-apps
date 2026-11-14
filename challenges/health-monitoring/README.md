# ASTRA — Astronaut Health Monitoring

An exploratory prototype with synthetic sensors, Python ingestion and validation, and a Flutter interface prototype. Step 1 and Step 2 are connected. Step 3 has a callable interface but no risk-assessment engine yet. The Python pipeline uses only the standard library.

## Layout

```text
health-monitoring/
  src/
    biosensors.py           # Step 1: existing synthetic story and noise generator
    ingest_validate/        # Step 2 and the connection to Step 3
      adapters.py           # Sensor packets -> individual observations
      validation.py         # Schema, timestamps, units, and plausibility
      service.py            # Raw audit records, clean SQLite history, duplicates
      pipeline.py           # Step 1 -> Step 2 -> optional assessment function
      cli.py                # Demo, JSON/JSONL ingestion, history export
      __init__.py           # Public Python functions
    app_frontend/           # Existing Flutter application and platform projects
  tests/
    test_ingest_validate.py # Validation and storage behavior
    test_pipeline.py        # Existing simulator and assessment interface
  docs/
    pipeline.md             # Contracts, assumptions, and connection examples
    task-plan.md            # Non-UI tasks, dependencies, and working-day schedule
```

Generated databases and exports belong in `data/` and are ignored by Git. The existing Flutter platform folders stay inside `src/app_frontend/` because they belong to that application.

## Run the connected mission demo

Run these commands from the repository root:

```bash
export PYTHONPATH="$PWD/challenges/health-monitoring/src"
python3 -m ingest_validate.cli --sensor-demo
python3 -m ingest_validate.cli --latest a --limit 250
```

The first command reads all 21 story packets from the existing `biosensors.py` functions without their sleep loop. It expands them into 252 observations across three crew members and stores them in `data/telemetry.sqlite`. On a fresh database, all 252 are accepted. Running the same demo again reports 252 duplicates. The demo prints the explicit simulation clock used for its future-dated mission timestamps, clean history for Step 3, and `assessment_status: "not_configured"`.

For the smaller unit-conversion demo:

```bash
python3 -m ingest_validate.cli --demo
```

Use a separate database for each demo if you want isolated results:

```bash
python3 -m ingest_validate.cli --sensor-demo --db data/mission.sqlite
```

## Read actual simulator output

The existing simulator writes JSON Lines. Its story timestamps have no timezone, so replay requires an explicit assumption. This example treats them as UTC and uses an explicit replay clock after the seven-day story ends:

```bash
python3 challenges/health-monitoring/src/biosensors.py > data/sensor-packets.jsonl
python3 -m ingest_validate.cli --sensor-input data/sensor-packets.jsonl \
  --assume-utc --reference-time 2026-11-22T00:00:00Z
```

Run a demo first to create `data/`, or create that directory before redirecting output. For other sensor streams, provide aware timestamps and use the real clock by omitting `--reference-time`. `--sensor-input -` also accepts JSON Lines from standard input. The current command ingests a finite batch atomically; an endless live stream needs bounded batches before production use.

For canonical Step 2 observations in a JSON array, use `--input observations.json`. Export validated history with `--latest <astronaut_id>`; JSON output can be redirected into a file for the assessment teammate.

## Verify

```bash
PYTHONPATH=challenges/health-monitoring/src python3 -m unittest discover -s challenges/health-monitoring/tests -v
```

The tests cover validation, unit conversions, raw retention, normalized duplicates, conflicts, transaction rollback, full mission ingestion, and the clean-history assessment interface.

## Remaining work

See the [pipeline contract](docs/pipeline.md) and [task schedule](docs/task-plan.md). Sensor semantics and assessment formulas still need team agreement. Official challenge requirements have not been recorded. All sensor examples here are synthetic; the prototype and its data-quality bounds are not clinically validated.
