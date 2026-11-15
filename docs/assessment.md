# Step 3: assessment and recovery

We assess validated observations, preserving valid measurements even when their values warrant a warning. The engine computes preceding-only median/MAD baselines, changes, time-based trends, and configurable consecutive-reading rules. Future readings cannot influence an earlier assessment. Rules can select a sensor source and require fresh data, a minimum time span, and a maximum sampling gap.

Every run requires an explicit versioned JSON policy. `config/assessment-demo.json` is a fictional policy restricted to synthetic observations. Its cardiovascular, immune, behavioral, and bone-loss scores are configured points, not probabilities or approved medical formulas. In particular, the bone-loss demonstration uses behavioral proxies; it does not measure bone loss. The newly published team notes and tables must be mapped into a reviewed executable policy before we can call the scoring policy complete.

Missing inputs, stale readings, insufficient baselines, and unusable features produce unknown results. We use `null` for an unknown score or warning level. Level 0 means an assessed green result; levels 1, 2, and 3 mean yellow, orange, and red. A partially assessed domain retains its unavailable reasons. Known positive metric warnings remain visible when other inputs are missing.

## Run the synthetic mission

From the repository root, after PocketBase setup and ingestion:

```bash
PYTHONPATH=src python3 -m astrocrates assess a --policy config/assessment-demo.json --all-days
PYTHONPATH=src python3 -m astrocrates assessments a
PYTHONPATH=src python3 -m astrocrates escalations --astronaut-id a
```

Repeat the assessment for crew `b` and `c`. Backfills evaluate each UTC day against history available by that day's end. Initial days can lack sufficient baseline data. A replay of the same policy and inputs reuses its durable job and result.

For new packets, `capture --process --assessment-policy config/assessment-demo.json --run-assessment` connects all three steps. The `process` command accepts the same assessment options. Without `--run-assessment`, jobs remain available for an independent worker. Persistent assessment jobs require PocketBase; the pure Python engine can also evaluate an explicit history without storage.

## Jobs and failures

```bash
PYTHONPATH=src python3 -m astrocrates assessment-worker --watch --interval 1
PYTHONPATH=src python3 -m astrocrates assessment-jobs --status failed
PYTHONPATH=src python3 -m astrocrates retry-assessment JOB_ID
```

We store the policy and input history with each job. Workers claim expiring leases; only the current claimant can complete a job. Completion writes the full assessment, known domain results, escalation events, and completed job status in one transaction. Unknown domains are retained in the full result without inventing green domain scores. Retries reuse the stored inputs without re-ingesting sensor packets. After the configured attempt limit, a deliberate retry requires `--reset-attempts`.

Orange/red severity increases create durable escalation events. Repeated warnings at the same severity do not create repeated events. Older backfills cannot rewind the current crew status or create a new current escalation. Events are stored for inspection; email, push, and other external notification delivery are not implemented.

## Step 2 monitoring

```bash
PYTHONPATH=src python3 -m astrocrates monitor a --max-age-seconds 86400 --expected-interval-seconds 86400 --reference-time 2026-11-22T00:00:00Z --policy mission-replay
PYTHONPATH=src python3 -m astrocrates alerts --astronaut-id a
```

We track freshness and sampling gaps per metric and source. Monitoring stores active, resolved, and reopened quality alerts. Use `--source` to isolate a device. Live monitoring uses `--watch --interval 30`; an explicit replay clock is limited to a single check. These are data-quality conditions, separate from health assessment and physical sensor calibration.
