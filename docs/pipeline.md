# Sensor, ingestion, and assessment contracts

## Current connection

```text
biosensors.py (synthetic packet)
  -> adapters.sensor_observations (one observation per metric)
  -> validation.validate_observation
  -> service.ingest_batch
       -> raw_measurements (every delivery)
       -> validated_observations (accepted, unique observations)
  -> pipeline.process_sensor_packets
       -> get_validated_observations (history per affected crew member)
       -> assess(astronaut_id, history), when provided by Step 3
```

Step 2 checks data quality. A valid heart rate of 135 bpm passes through without a health-risk label. Health interpretation belongs to the assessment engine, which is not implemented in this repository.

## Sensor adapter

The adapter expects the full packet emitted by `src/biosensors.py`. It maps `crew_id` to `astronaut_id` and `timestamp` to `captured_at`.

| Sensor field | Step 2 metric | Unit |
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

The `hr` and `hrv` mappings are prototype assumptions: the generator does not specify resting conditions or the HRV method. Confirm resting HR and RMSSD with the sensor owner before using these names for other data. Do not apply this adapter to real sensors without a separate schema and provenance agreement.

The adapter marks data as simulated and uses `synthetic_biosensors` as its source. It retains the entire original sensor packet on each expanded raw observation under `sensor_packet`; the repetition keeps the existing raw storage schema simple. Extra packet fields remain in this audit payload but are not emitted as new metrics. Missing metric values are quarantined individually, so a bad SpO2 field does not discard otherwise valid measurements. A malformed non-object packet produces one quarantined delivery.

Naive timestamps are invalid by default. `assume_utc=True` explicitly interprets them as UTC and records that assumption in observation context. The mission demo opts into this assumption and validates against a simulation clock. Other input uses the real clock unless the caller explicitly passes an aware `reference_time` for replay.

## Step 3 interface

```python
from ingest_validate import process_sensor_packets

# risk_engine.assess must be implemented by the Step 3 owner.
result = process_sensor_packets(
    sensor_packets,
    db_path="data/telemetry.sqlite",
    assume_utc=True,  # Only if the sensor contract explicitly says UTC.
    assess=risk_engine.assess,
)
```

`assess` receives `(astronaut_id, history)` and returns an assessment result owned by Step 3. Each history item contains `astronaut_id`, `metric`, `value`, `unit`, `captured_at`, `source`, `context`, and `quality_flags`. History is newest first and defaults to the latest 250 observations; use `history_limit` to set the observation count needed for the assessment window, up to 10,000. This is a count of individual metrics, not mission days.

The pipeline calls the assessor once per crew member with newly accepted observations. Quarantines, duplicates, and conflicts do not trigger it alone. No assessor means the result includes `step3_history` and `assessment_status: "not_configured"`. This makes the interface demonstrable without inventing risk formulas.

Ingestion commits before assessment. If assessment fails, the clean records remain available through `get_validated_observations`; retry assessment against that history. Replaying an unchanged sensor batch will be treated as duplicates and will not retry the assessor automatically. Durable assessment jobs, result persistence, API transport, and delivery retries are remaining tasks.

## Storage rules

Identity is `(astronaut_id, metric, UTC captured_at, source)`. An identical normalized value, unit, and context is a duplicate; changed content at the same identity is a conflict. The first accepted record is preserved. Timestamp aliases and supported unit conversions normalize before comparison.

All deliveries retain raw payloads, ingestion status, and error reasons. Non-JSON Python objects retain a diagnostic representation. Clean history excludes quarantined and conflicting records. SQLite serializes writers and stores each finite batch atomically.

The source string is a provenance label, not authentication. Rolling baselines, sensor reliability, missing-data alerts, risk scoring, and real sensor authentication remain separate work items in the [task plan](task-plan.md).
