# Capture, validation, and assessment contracts

```text
Step 1: synthetic sensor packet with capture timestamp
  -> durable sensor_packets inbox (pending, original payload stored once)
Step 2: bounded worker reads pending packets
  -> adapter expands one observation per metric
  -> validator checks formatting, units, timestamps, and plausibility
  -> transaction commits per-metric outcomes + clean observations + processed marker
Step 3: clean historical observations
  -> optional assessment function / authenticated history API
  -> risk calculations still to be implemented
```

Step 1 persists data before validation. Invalid packets remain available for inspection. Step 2 never assigns health-risk labels: a heart rate of 135 bpm can pass data-quality checks. Step 3 owns interpretation.

## Sensor mapping

The adapter expects the existing full `src/biosensors.py` packet, maps `crew_id` to `astronaut_id`, and maps `timestamp` to `captured_at`.

| Sensor field | Normalized metric | Unit |
| --- | --- | --- |
| `hr` | `hr_resting` | `bpm` |
| `hrv` | `hrv_rmssd` | `ms` |
| `spo2` | `spo2` | `%` |
| `temp_c` | `temp_c` | `C` |
| `radiation_msv_cumulative` | same | `mSv` |
| `sleep_h` | same | `h` |
| `sleep_quality`, `mood` | same | `score_1_5` |
| `symptoms` | same | `list` |
| `exercise_logged`, `social_interaction` | same | `bool` |
| `mission_day` | same | `day` |

Resting HR and RMSSD are prototype assumptions that still need confirmation with the sensor owner. Data is labeled simulated and sourced from `synthetic_biosensors`; that label does not authenticate a physical device. Extra fields remain in the original payload. Missing metric fields are quarantined individually. Non-object packets and diagnostic representations of non-JSON inputs are quarantined as whole deliveries.

## Timestamps and delivery identity

Capture time belongs to the sensor. Receive time belongs to storage and always uses the actual UTC clock. Validation compares against the original receive time, or an explicitly stored simulation clock; it does not use a later retry time. Invalid timestamps can be stored raw but cannot enter clean history.

Naive timestamps are rejected unless the caller explicitly sets `assume_utc=True`; that assumption is recorded in context. The existing synthetic story remains unchanged, and the new capture command explicitly assigns its simulation clock. The noise command interprets the original generator's local timestamps in the machine's local timezone and converts them to aware UTC before storage.

Every new delivery is retained. PocketBase additionally accepts a producer-scoped delivery key so a timed-out capture can be retried without inserting another raw row. That key is different from observation identity: `(astronaut_id, metric, UTC captured_at, source)`. Identical normalized value, unit, and context at that identity is a duplicate; changed content is a conflict. The first accepted record stays in place.

## Storage and retry behavior

Both backends store the packet once, link per-metric outcomes to it, and atomically commit clean observations with the processed marker. SQLite uses `raw_measurements.sensor_packet_id`; PocketBase uses related `validation_results` records. Old local audit rows remain intact with a nullable packet link after migration.

SQLite locks a bounded worker batch. PocketBase commits each packet through a server transaction. Concurrent workers cannot commit the same packet twice. A storage or validation failure rolls back the corresponding transaction, leaving packets pending for retry. A packet containing invalid measurements can still be marked processed: its quarantines and reasons are the completed validation outcome.

`capture` and `process` can run separately. Capturing without the worker proves raw data is already durable. `capture --process` runs them together for a small demo. PocketBase is accessed over its APIs; direct writes into its internal SQLite files are not supported. Local SQLite and PocketBase databases are independent and are not automatically synchronized.

## Step 3 contract

A clean observation has `astronaut_id`, `metric`, `value`, `unit`, `captured_at`, `source`, `context`, and `quality_flags`. History is newest first. Limits count individual metrics, not mission days. Default history is 250 observations, configurable up to 10,000; the assessment owner must choose a suitable window.

For the local Python connection:

```python
from ingest_validate import process_sensor_packets

# risk_engine.assess is supplied by the Step 3 owner.
result = process_sensor_packets(
    sensor_packets,
    db_path="data/telemetry.sqlite",
    assume_utc=True,  # Only when the source contract explicitly says UTC.
    assess=risk_engine.assess,
)
```

The callback receives `(astronaut_id, history)` once per crew member with newly accepted data. It is not triggered by duplicates or quarantines alone. The callback path and `get_validated_observations` remain compatible with the original Python interface.

For shared API storage:

```python
from ingest_validate.pocketbase import PocketBaseTelemetry

store = PocketBaseTelemetry.from_environment()
history = store.get_history("a", limit=250)
assessment = risk_engine.assess("a", history)
```

The commands also export `step3_history` after processing. Without an actual risk engine, they explicitly report `assessment_status: "not_configured"`.

Ingestion completes before assessment. Failed assessments can reread clean history; replaying duplicate measurements does not automatically retry a callback. Durable assessment jobs, result persistence, crew-specific frontend authorization, missing-data monitoring, and agreed risk formulas remain tasks in the [schedule](task-plan.md). See [PocketBase setup](../backend/pocketbase/README.md) for collection rules and real API tests.
