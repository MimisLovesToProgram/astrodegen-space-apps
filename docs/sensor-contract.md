# Step 1 → Step 2 → Step 3 data contract

Contract version: `astrocrates.observation.v1`. The executable specification is generated from the validator and adapter rules:

```bash
PYTHONPATH=src python3 -m astrocrates contract
```

## Sensor input

The existing simulator supplies full packets containing `crew_id`, `timestamp`, and the twelve fields in `SENSOR_FIELDS` in `src/ingest_validate/adapters.py`. Each packet is stored before validation. The prototype interprets `hr` as resting HR in bpm and `hrv` as RMSSD in milliseconds. These assumptions are explicit; the physical sensor owner must confirm them before real device data is used.

Canonical individual observations require `astronaut_id`, `metric`, `value`, `unit`, `captured_at`, and `source`. Optional context carries provenance such as `simulated: true`. The contract command lists supported metrics, units, value types, and current prototype bounds.

Timestamps must be timezone-aware. Naive timestamps are invalid unless the capture caller explicitly assumes UTC, which is recorded in context. The fixed synthetic story uses an explicit simulation clock; noise timestamps are converted from the generator machine's local clock to UTC. Capture time, actual receive time, and an optional replay clock are separate values.

Sampling frequency is not inferred. The story supplies one packet per crew per simulated day; continuous noise uses the command's tick interval. Quality reports require an explicit maximum age, so a daily mission story is not judged against a continuous-stream cadence.

## Validation and storage

Step 2 normalizes supported units, rejects malformed or implausible data, and retains all original deliveries. Clean identity is `(astronaut_id, metric, normalized captured_at, source)`. Matching content is a duplicate; changed content is a conflict, and the first accepted observation is preserved.

Validation is a data-quality check. Valid changes in physiology remain available to assessment. Data acceptance rates describe recorded validation outcomes and do not claim calibrated hardware accuracy or medical safety.

## Assessment handoff

```bash
PYTHONPATH=src python3 -m astrocrates --env-file .env.reader handoff a --limit 250
```

The export contains `contract_version`, `astronaut_id`, `generated_at`, `order`, `observation_limit`, `may_be_truncated`, and `observations`. Each observation contains the six canonical fields plus normalized `context` and `quality_flags`. Results are newest first. The default limit is 250 individual observations, not 250 mission days; the maximum is 10,000. The assessment owner must choose the window needed by the actual formulas.

The existing `history` command and Python callback keep their original list format. The versioned `handoff` command is an additional interface. A seven-day synthetic story has 84 observations per crew, so it fits within the default window.

The contract and export are implemented and verified. Acceptance by the Step 1/Step 3 owners and integration with a real risk engine remain team handoff tasks; no health-risk calculations are included in Step 2.

## Assessment results and crew delivery

We now persist policy-versioned assessments and retryable jobs separately from validation outcomes. The supplied policy is explicitly synthetic-only; team-note formulas are executable with provisional color bands. Unknown assessment levels are `null`, while assessed warning levels are integers 0–3. The crew API returns the latest validated value per UTC day and metric, with a warning only for the exact assessed observation. See the [assessment guide](assessment.md) and [frontend contract](frontend-api.md) for aliases, authentication, and the complete daily-history response.
