# PocketBase backend

PocketBase owns its database and exposes the record APIs used by Astrocrates. Python communicates over HTTP; it never writes into `pb_data`. The migrations and hooks are tested against the official **PocketBase v0.42.2** Linux binary. Keep that version for a reproducible demo; test migrations before upgrading.

## Start locally

The executable is installed at `backend/pocketbase`. On a fresh installation, create the first administrator through PocketBase's installer before running service setup. Existing administrators and data are preserved.

From the repository root, while the local server is stopped:

```bash
PYTHONPATH=src python3 -m ingest_validate.setup --seed-demo-users
```

Setup backs up an existing database, applies migrations, starts PocketBase at `http://127.0.0.1:8090`, and provisions ingest/worker/reader accounts. It uses a temporary provisioning administrator, then removes that account. The original administrator's credentials are unchanged. A rerun reuses existing service credentials and refuses an occupied port instead of replacing a running server.

Credentials are generated into ignored files with owner-only permissions: `.env` for the worker, `.env.ingest` for capture, and `.env.reader` for clean history. They are never printed or committed. The CLI loads `.env` automatically; `--env-file` selects another role, and exported environment variables take precedence. Existing settings are checked rather than overwritten. Setup logs and its server PID are under ignored `data/` paths.

The setup command leaves the local server running. Stop that server before rerunning setup. The dashboard is at `http://127.0.0.1:8090/_/`; use your existing administrator account there.

## Capture first, validate later

From the repository root:

```bash
# Step 1: 21 original packets become durable pending records.
PYTHONPATH=src python3 -m astrocrates --env-file .env.ingest capture --interval 0

# Step 2: validate up to 100 pending packets, atomically per packet.
PYTHONPATH=src python3 -m astrocrates process

# Step 3 input: read the clean history for crew member a.
PYTHONPATH=src python3 -m astrocrates --env-file .env.reader history a
```

For a single demo command, use `capture --interval 0 --process`. For continuous synthetic noise, use `capture --mode noise --interval 3`; run `process --watch --interval 1` in another terminal. Add `--ticks 10` to bound a noise run. Stop either process with Ctrl+C; committed packets and validation results remain available. Finite work batches keep transactions short.

## Collections and API boundaries

| Collection | Content | Access |
| --- | --- | --- |
| `telemetry_services` | Authenticated service accounts and roles | Administrator provisions accounts; services can read their own account |
| `sensor_packets` | One original payload per delivery, capture/receive clocks, pending/processed state | Worker reads; custom capture route writes |
| `validation_results` | Per-metric status and reasons, related to the original packet | Worker reads; commit route writes |
| `validated_observations` | Unique normalized observations and provenance | Worker and reader services read; commit route writes |

`ingest` accounts can capture only. `worker` accounts can capture, process, and read. `reader` accounts can read clean history. Collection mutation is locked outside the custom routes. Crew logins use a separate `users` collection linked to an astronaut profile. Optional demo crew credentials are generated in private `.env.crew-a`, `.env.crew-b`, and `.env.crew-c` files. Frontend source is unchanged.

- `POST /api/astrocrates/capture` persists a packet without measurement validation. A producer-scoped `delivery_key` makes network retries idempotent. The Python client retries a transient capture failure once using the same key; callers can supply a stable key for a later retry. Replaying with a new key records a new delivery, then Step 2 detects duplicate observations.
- `POST /api/astrocrates/commit` saves all metric outcomes, new clean observations, and the processed marker in one transaction. Concurrent workers cannot commit a packet twice. The route trusts the authenticated Python worker's data-quality validation.
- Built-in record APIs support filtered history reads. For example: `GET /api/collections/validated_observations/records?filter=astronaut_id%3D%22a%22&sort=-captured_at` with an authorized service token. Normalized measurements are in each record's `observation` field. Python's `get_history` unwraps these records.

Receive timestamps come from PocketBase. Sensor timestamps remain in the raw packet even when malformed. A supplied simulation clock is stored separately; without it, validation uses the original receive time, so delaying a worker does not make a future-dated packet valid. A failed commit leaves the packet pending; restart processing to retry it.

## Existing local SQLite data

The offline SQLite backend is still available via `--backend sqlite`. Existing local databases migrate in place when opened and keep their old records. PocketBase uses its own database; this integration does not automatically import or synchronize earlier local telemetry. If PocketBase is unavailable, capture reports the failure; it does not silently switch databases.

## Verify the real API

From the repository root, with the downloaded executable:

```bash
POCKETBASE_TEST_BINARY="$PWD/backend/pocketbase" \
  PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Tests launch an isolated server and database in a temporary directory, use generated test credentials, and stop the server afterward. They cover the complete mission, permissions, retries, conflict detection, rollback, and concurrent workers. No application accounts are created on your running backend.

Implementation references: [records APIs](https://pocketbase.io/docs/api-records/), [collections](https://pocketbase.io/docs/collections/), [migrations](https://pocketbase.io/docs/js-migrations/), and [transactions](https://pocketbase.io/docs/js-database/).

## Current local workspace

Use `/home/evantampa129/astrodegen-space-apps` as the single active project directory. The local executable and the existing database were consolidated into this folder from an older clone. Its original contents are preserved in the ignored `data/backups/project-copy-before-consolidation.tar.gz` archive at the project root. Downloaded installation files remain in Downloads.

The complete setup, contract, monitoring, and API test suite passes against the installed v0.42.2 executable using temporary data. The actual local database now has the Astrocrates migration applied and all three service roles configured. The original administrator was verified unchanged. A live-backend check produced 252 clean observations from 21 mission packets; follow-up replay, quarantine, and conflict checks kept the clean count at 252. The local backend is configured. Durable Step 3 jobs, assessments, escalation events, and crew APIs are implemented; the final scoring policy and frontend integration remain pending.

## Quality reporting and Step 3 export

```bash
# Daily-story freshness uses an explicit simulation clock and a one-day age policy.
PYTHONPATH=src python3 -m astrocrates quality a --max-age-seconds 86400 \
  --reference-time 2026-11-22T00:00:00Z
PYTHONPATH=src python3 -m astrocrates --env-file .env.reader handoff a --limit 250
PYTHONPATH=src python3 -m astrocrates contract
```

The quality command reports missing expected metrics, stale readings, future-clock mismatches, and whether its queried history may be truncated. `--metrics` can narrow the expected metric set. A worker-only aggregate API, `GET /api/astrocrates/quality-summary`, supplies database-wide outcome counts and pending/processed packet counts without downloading every raw record. The report labels those audit counts as `all_database`; they are not restricted to the queried crew.

Per-source data acceptance rate is `accepted / (accepted + quarantined + conflicts)`. Duplicates are reported separately and cannot inflate the rate. This is a data-quality indicator, not a clinical score or calibrated sensor-reliability estimate.

The local verification record and sample handoff exports are in ignored `data/step2-verification.json`, `data/observation-contract-v1.json`, and `data/step3-history-a.json`. Original mission packets plus follow-up audit checks currently account for 44 processed deliveries and 252 clean observations. These are synthetic demo records. See the [versioned sensor contract](../docs/sensor-contract.md) for the Step 1/2/3 boundary.

## Assessment and crew APIs

Step 3 adds `assessment_jobs`, `assessment_runs`, and `escalation_events`. The existing `domain_assessments` table stores known domain scores linked to a run. Quality monitoring uses `quality_checks` and `quality_alerts`. Workers use authenticated custom routes for job claims, completion, failure, retry, and quality updates; reader services can inspect results. Crew users can only read their linked profile and daily sensor history through the crew routes.

See [assessment commands and recovery](../docs/assessment.md) and [login, sensors, and profile contracts](../docs/frontend-api.md). `--seed-demo-users` is optional and never prints generated passwords. The managed server remains bound to `127.0.0.1`; sharing it across laptops needs an explicitly configured host and network access.
