# Project decisions

## Initial exploration (historical)

- Use one repository for ASTRODEGEN's Space Apps exploration.
- Keep a separate folder per challenge under `challenges/`.
- Begin with the astronaut health monitoring concept, ASTRA.
- Track alternative ideas in `ideas/` so the team can change direction without discarding previous work.
- Official challenge selection remains pending.

## Astrocrates prototype

The project is now named **Astrocrates**. ASTRODEGEN remains the team/repository identity. The team selected a single application layout: `frontend/`, `src/`, `backend/`, `tests/`, and `docs/`. The former `challenges/health-monitoring/` wrapper and unused `ideas/` and `shared/` placeholder folders were removed. Existing Flutter files and Python package names are preserved. Official challenge selection is still pending.

## Durable capture and shared API backend

Step 1 stores raw timestamped packets before validation. Step 2 processes the pending inbox and commits metric results together with processed markers. Raw packets are stored once per delivery, rather than repeated in every metric's audit payload. PocketBase supplies the shared API backend; local SQLite remains an explicit offline development option. They are independent stores, without automatic synchronization. PocketBase migrations and hooks are tested against v0.40.6.

## Restore the frontend location

The Flutter app is back at `src/app_frontend/`, preserving its original files, contents, and platform folder layout. The root-level `frontend/` folder was moved without changes to the Flutter project.
