# Project decisions

## Initial exploration (historical)

- Use one repository for ASTRODEGEN's Space Apps exploration.
- Keep a separate folder per challenge under `challenges/`.
- Begin with the astronaut health monitoring concept, ASTRA.
- Track alternative ideas in `ideas/` so the team can change direction without discarding previous work.
- Official challenge selection remains pending.

## Astrocrates prototype

The project is now named **Astrocrates**. ASTRODEGEN remains the team/repository identity. The canonical application layout is `src/` (including `src/app_frontend/`), `backend/`, `tests/`, and `docs/`. Legacy challenge and idea folders reappeared in team merges and were consolidated in the cleanup described below. Existing Flutter files and Python package names are preserved. Official challenge selection is still pending.

## Durable capture and shared API backend

Step 1 stores raw timestamped packets before validation. Step 2 processes the pending inbox and commits metric results together with processed markers. Raw packets are stored once per delivery, rather than repeated in every metric's audit payload. PocketBase supplies the shared API backend; local SQLite remains an explicit offline development option. They are independent stores, without automatic synchronization. PocketBase migrations and hooks are tested against v0.42.2.

## Restore the frontend location

The Flutter app is back at `src/app_frontend/`, preserving its original files, contents, and platform folder layout. The root-level `frontend/` folder was moved without changes to the Flutter project.

## Complete the canonical layout

The latest team frontend was copied into `src/app_frontend/`, with file hashes checked before removing its obsolete challenge wrapper. Previous canonical files and legacy documentation were backed up locally. Team reference tables moved to `src/assessment/team_data.py`, and notes moved to `docs/team-health-rules.md`. The startup-only duplicate engine and empty exploration placeholders were removed. Flutter now calls the authenticated crew APIs.
