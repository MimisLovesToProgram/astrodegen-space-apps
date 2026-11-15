# Step 3: assessment and recovery

We assess validated observations, preserving valid measurements even when their values warrant a warning. The engine computes preceding-only median/MAD baselines, changes, time-based trends, and configurable consecutive-reading rules. Future readings cannot influence an earlier assessment. Rules can select a sensor source and require fresh data, a minimum time span, and a maximum sampling gap.

Every run requires an explicit versioned JSON policy. `config/assessment-demo.json` is a fictional policy restricted to synthetic observations. Its cardiovascular, immune, behavioral, and bone-loss scores are configured points, not probabilities or approved medical formulas. In particular, the bone-loss demonstration uses behavioral proxies; it does not measure bone loss. The team prototype rules are now executable in `config/assessment-team.json`; the fictional demo policy remains available as a separate fixture.

Missing inputs, stale readings, insufficient baselines, and unusable features produce unknown results. We use `null` for an unknown score or warning level. Level 0 means an assessed green result; levels 1, 2, and 3 mean yellow, orange, and red. A partially assessed domain retains its unavailable reasons. When known points already prove a warning, we preserve its level and lower-bound score with `score_is_lower_bound=true`; it is not marked complete. Missing inputs cannot erase an already established escalation. Known positive metric warnings remain visible when other inputs are missing.

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

## Team prototype policy

We preserve the source notes in [team-health-rules.md](team-health-rules.md) and their reference tables in `src/assessment/team_data.py`. The one executable assessment entry point is the `assessment` package through `python3 -m astrocrates assess`; the startup-only duplicate engine was removed.

`config/assessment-team.json` uses sensor readings from `synthetic_biosensors` and actual user logs from `crew_checkin`. `config/assessment-team-synthetic.json` applies the same rules to synthetic history only. Select a policy explicitly; neither silently replaces the old fictional demo fixture. These are team prototype rules, not clinically approved limits.

We use the latest reading per UTC date for daily streaks. Baselines use the median of the latest readings from each of the preceding seven complete UTC dates, excluding the current date. Multiple readings on one day cannot substitute for missing days. Each point of a multi-day HR streak uses its own preceding baseline. The seven-day sample mission therefore cannot supply all required baseline windows; early unknown results are expected.

Social absence uses actual elapsed hours since the last positive log. Exercise absence uses the strict greater-than-14-days condition. We require ongoing reporting with a maximum 36-hour gap; missing reports remain unknown. If no previous positive log is available, a continuous sequence of negative logs can only prove a lower bound on elapsed absence. The bone model counts two points per explicitly negative mission day from mission day 1, requires complete matching exercise/mission-day coverage, and adds twenty points when exercise absence exceeds fourteen days. Daily logs are a reporting assumption, not proof of physical activity.

Symptom points require `sore throat` or `fatigue`, rather than any nonempty symptom list. Activity compares `activity_pct_target` with 50%; a boolean exercise answer is never converted into a percentage. Missing activity remains unknown.

As provisionally agreed, Yellow starts at 20 points and Red at 80. Orange starts at the source-note thresholds: immune 60, cardiovascular 55, behavioral 50, and bone loss 50. The cardiovascular and behavioral rule totals cannot reach 80, so they currently top out at Orange. Color-band review remains a team task. Rule-level warnings use Yellow; the domain aggregation determines Orange/Red and escalation.

To process incoming check-ins:

```bash
PYTHONPATH=src python3 -m astrocrates process --watch --interval 1 --assessment-policy config/assessment-team.json --run-assessment
```

Older results from any policy cannot rewind the shared crew profile. Each result retains its policy identity and unavailable reasons. No external notifications are sent by these commands.
