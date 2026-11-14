# PocketBase backend

PocketBase owns its database and exposes the record APIs used by Astrocrates. Python communicates over HTTP; it never writes into `pb_data`. The migrations and hooks are tested against the official **PocketBase v0.40.6** Linux binary. Keep that version for a reproducible demo; test migrations before upgrading.

## Start locally

1. Download the matching executable from the [official release](https://github.com/pocketbase/pocketbase/releases/tag/v0.40.6), verify its published checksum, and put the executable in this folder. Runtime binaries are ignored by Git.
2. From this folder run `./pocketbase serve --http=127.0.0.1:8090`. The committed migration creates the telemetry collections automatically. Use the installer link printed by PocketBase to create your local administrator account.
3. In the dashboard, create a record in the `telemetry_services` auth collection with an email, password, and role `worker`. This account can capture and validate synthetic telemetry for the demo. There are no default application credentials.
4. In a terminal at the repository root, configure the Python client:

```bash
export POCKETBASE_URL=http://127.0.0.1:8090
export POCKETBASE_EMAIL=worker@example.com
read -r -s -p 'PocketBase service password: ' POCKETBASE_PASSWORD
export POCKETBASE_PASSWORD
```

Alternatively set `POCKETBASE_TOKEN` to an existing service token. Tokens take precedence over email/password. The `.env.example` lists the settings; the Python standard-library client reads the environment and does not automatically load `.env` files.

## Capture first, validate later

From the repository root:

```bash
# Step 1: 21 original packets become durable pending records.
PYTHONPATH=src python3 -m astrocrates capture --interval 0

# Step 2: validate up to 100 pending packets, atomically per packet.
PYTHONPATH=src python3 -m astrocrates process

# Step 3 input: read the clean history for crew member a.
PYTHONPATH=src python3 -m astrocrates history a
```

For a single demo command, use `capture --interval 0 --process`. For continuous synthetic noise, use `capture --mode noise --interval 3`; run `process --watch --interval 1` in another terminal. Add `--ticks 10` to bound a noise run. Stop either process with Ctrl+C; committed packets and validation results remain available. Finite work batches keep transactions short.

## Collections and API boundaries

| Collection | Content | Access |
| --- | --- | --- |
| `telemetry_services` | Authenticated service accounts and roles | Administrator provisions accounts; services can read their own account |
| `sensor_packets` | One original payload per delivery, capture/receive clocks, pending/processed state | Worker reads; custom capture route writes |
| `validation_results` | Per-metric status and reasons, related to the original packet | Worker reads; commit route writes |
| `validated_observations` | Unique normalized observations and provenance | Worker and reader services read; commit route writes |

`ingest` accounts can capture only. `worker` accounts can capture, process, and read. `reader` accounts can read clean history. Collection mutation is locked outside the custom routes. These are backend service roles, not the future crew-specific Flutter login model; no frontend credentials or code were changed.

- `POST /api/astrocrates/capture` persists a packet without measurement validation. A producer-scoped `delivery_key` makes network retries idempotent. The Python client retries a transient capture failure once using the same key; callers can supply a stable key for a later retry. Replaying with a new key records a new delivery, then Step 2 detects duplicate observations.
- `POST /api/astrocrates/commit` saves all metric outcomes, new clean observations, and the processed marker in one transaction. Concurrent workers cannot commit a packet twice. The route trusts the authenticated Python worker's data-quality validation.
- Built-in record APIs support filtered history reads. For example: `GET /api/collections/validated_observations/records?filter=astronaut_id%3D%22a%22&sort=-captured_at` with an authorized service token. Normalized measurements are in each record's `observation` field. Python's `get_history` unwraps these records.

Receive timestamps come from PocketBase. Sensor timestamps remain in the raw packet even when malformed. A supplied simulation clock is stored separately; without it, validation uses the original receive time, so delaying a worker does not make a future-dated packet valid. A failed commit leaves the packet pending; restart processing to retry it.

## Existing local SQLite data

The offline SQLite backend is still available via `--backend sqlite`. Existing local databases migrate in place when opened and keep their old records. PocketBase uses its own database; this integration does not automatically import or synchronize earlier local telemetry. If PocketBase is unavailable, capture reports the failure; it does not silently switch databases.

## Verify the real API

From the repository root, with the downloaded executable:

```bash
POCKETBASE_TEST_BINARY="$PWD/backend/pocketbase/pocketbase" \
  PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Tests launch an isolated server and database in a temporary directory, use generated test credentials, and stop the server afterward. They cover the complete mission, permissions, retries, conflict detection, rollback, and concurrent workers. No application accounts are created on your running backend.

Implementation references: [records APIs](https://pocketbase.io/docs/api-records/), [collections](https://pocketbase.io/docs/collections/), [migrations](https://pocketbase.io/docs/js-migrations/), and [transactions](https://pocketbase.io/docs/js-database/).
