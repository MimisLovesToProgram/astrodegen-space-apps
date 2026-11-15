# Project index

This file lists what we reorganized on this branch and where everything lives now. Pull the branch to get the same layout.

## What changed

| Before | Now | Why |
| --- | --- | --- |
| `challenges/health-monitoring/src/` | `src/` | One source folder at the root instead of a second copy inside `challenges/` |
| `challenges/health-monitoring/src/app_frontend/` | `src/app_frontend/` | One Flutter app; the latest team screens are kept here |
| `challenges/health-monitoring/tests/` | `tests/` | All Python and PocketBase tests in one place |
| `challenges/health-monitoring/docs/`, `README.md` | `docs/`, `README.md` | One set of documentation |
| `ideas/README.md`, `shared/README.md` | Removed | Empty placeholder folders |
| `backend/pb_data/` (committed databases) | Not in Git | Runtime data is created locally by the setup command |
| Feature PocketBase hooks and migrations | `backend/unmerged/` | Preserved for review and not loaded by PocketBase |
| `backend/pocketbase` (executable) | Not in Git | Each person downloads it locally; see `backend/README.md` |

The `challenges/` folder no longer exists in Git. If an old copy remains on your disk after pulling, it is untracked and can be deleted.

## Where things are

```text
README.md            Project overview and test command
AGENTS.md            Writing rules for project content
INDEX.md             This file
src/
  biosensors.py      Step 1: synthetic sensor data
  astrocrates.py     Pipeline commands (capture, process, assess, ...)
  ingest_validate/   Step 2: capture, validation, storage, quality alerts
  assessment/        Step 3: rules, scoring, assessment jobs
  app_frontend/      Flutter app (login, check-in, dashboard, history)
backend/
  pb_hooks/          PocketBase API routes kept from main
  pb_migrations/     Active PocketBase schema kept from main
  unmerged/          Feature hooks and migrations held for review; not loaded by PocketBase
  README.md          How to install and start the backend
config/              Assessment policies (team, synthetic, demo)
tests/               Python, PocketBase, and frontend integration tests
docs/                API contract, assessment rules, pipeline, task plan
```
