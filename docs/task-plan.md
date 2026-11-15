# Astrocrates tasks and schedule

This board covers the pipeline, backend, connected Flutter client, and remaining team demo work. We distinguish implemented mechanisms from provisional policy decisions. The bundled mission is synthetic.

| ID | Task | State | Remaining work or evidence |
| --- | --- | --- | --- |
| T01 | Agree official challenge requirements and demo scope | Pending team decision | Record the brief, source URL, and demo acceptance criteria |
| T02 | Supply synthetic sensor scenarios | Implemented | Three crew members, seven days, and a noise generator |
| T03 | Confirm real sensor semantics and time contract | Pending team decision | Confirm resting HR, RMSSD, units, sources, UTC clocks, cadence, and radiation semantics |
| T04 | Validate measurement schema, units, clocks, and plausibility | Implemented | Invalid inputs, conversions, and valid high HR are tested |
| T05 | Persist raw and clean data, duplicates, conflicts, and recovery | Implemented | Atomic packet processing and replay tests on SQLite and PocketBase |
| T06 | Connect simulator to storage and validation | Implemented with documented assumptions | 21 mission packets yield 252 unique clean observations |
| T07 | Supply clean history and a versioned assessment interface | Implemented | Configurable history, source filters, and handoff export |
| T08 | Agree assessment formulas and expected outcomes | Provisional policy implemented | Source-note points and Orange thresholds are executable; Yellow=20 and Red=80 were provisionally agreed and still need final review |
| T09 | Implement four-domain assessment calculations | Implemented with provisional bands | Calendar-day baselines/streaks, named symptoms, elapsed-time rules, activity percentage, and mission-day points are tested |
| T10 | Persist results and retry failed assessments | Implemented | Frozen inputs/policy, leases, atomic completion, idempotency, failed-job retry and attempt limits |
| T11 | Connect capture, processing, assessment, and backend APIs | Backend and client implemented | Login, profile, full daily history, typed crew check-ins, token handling, and visible unknown levels are connected |
| T12 | Monitor data quality and escalation conditions | Prototype implemented | Missing/stale data, per-source gaps, durable quality recovery, and orange/red transitions tested; physical calibration and external notification delivery remain pending |
| T13 | Verify the demo and hand off to teammates | Automated verification implemented; joint demo pending | Python/PocketBase and Flutter regression tests; device/network rehearsal and presentation still needed |

## Team handoff tasks

| Task | State | Next action |
| --- | --- | --- |
| Crew login API | Implemented | Connected Flutter client sends username/password and retains its crew token in memory |
| Sensor-history API | Implemented | Connected Flutter client sends crewId with token and displays levels 0–3 plus unknown `null` |
| Shared database setup | Local server configured | Agree the host and explicitly configure access from teammates' machines; managed setup remains localhost |
| UI integration | Implemented; device rehearsal pending | Real login/history/profile/check-in calls and unknown-state rendering; verify on the team devices |
| Final scoring policy | Implemented provisionally | Source-note rules are executable; review color bands and the documented reporting assumptions |
| External notifications | Pending if required by scope | Choose delivery channel and recipients before implementing outbound messages |
| Physical sensors | Pending if required by scope | Confirm devices, authenticity, calibration, and sampling policies |
| Repository cleanup | Implemented | One frontend in src/app_frontend, one assessment package, preserved team tables and notes, obsolete wrappers removed after backups |
| Official brief and presentation | Pending team decision | Agree scope and rehearse the integrated demo |

## Proposed next-session schedule

| Order | Work | Exit condition |
| --- | --- | --- |
| 1 | Confirm T01/T03/T08 and choose the shared host | Agreed scope, sensor semantics, scoring policy, and connection settings |
| 2 | Review and merge the backend feature branch through dev | Migrations and API contract reviewed; backend tests pass |
| 3 | Run the connected Flutter client on team devices | Login/history/check-in work with a real token; cross-crew access fails; unknown states are visible |
| 4 | Review provisional policy | Team confirms temporary score bands and time/reporting assumptions |
| 5 | Run the full team demo and recovery checks | Capture → validation → assessment → UI works; retries do not duplicate results |

These are dependency-ordered tasks, not assigned calendar deadlines. Team owners still need to agree delivery dates.

## Verification

The backend suite contains 106 tests, including isolated real-PocketBase servers, all three crew histories, permission boundaries, API response types, rate limiting, source filtering, job leases, retries, escalation deduplication, and backfills. It runs without changing the team's active database. The standard-library-only run skips PocketBase tests unless `POCKETBASE_TEST_BINARY` is set.

The original administrator, raw sensor deliveries, and validated observations are preserved during local setup. Generated binaries, databases, credentials, logs, and verification artifacts remain ignored. See the [assessment guide](assessment.md), [frontend API contract](frontend-api.md), and [backend setup](../backend/README.md). Flutter now uses the real crew APIs. Its seven regression tests cover token isolation, typed inputs, visible unknown states, per-crew reminders, and slider answer updates. An additional integration test runs the real Dart client against an isolated PocketBase and Python assessment worker.

## Canonical files and policy status

The preserved team specification is `docs/team-health-rules.md`; reference tables live in `src/assessment/team_data.py`. The executable engine is `src/assessment/engine.py`, with temporal features in `src/assessment/temporal.py`. The startup-only duplicate engine and legacy frontend wrapper are removed. The latest team Flutter work is preserved in `src/app_frontend/`.

Team policies are `config/assessment-team.json` for actual crew check-ins with sensor history and `config/assessment-team-synthetic.json` for synthetic replay. The original fictional `assessment-demo.json` remains a separate fixture. Baselines use seven prior complete UTC dates; streaks use calendar days; social/exercise absence uses elapsed time with explicit reporting-gap checks. Missing history stays unknown, and confirmed warning points remain lower bounds rather than being discarded.

Yellow=20 and Red=80 are provisional as agreed. Orange uses the domain thresholds in the notes. Cardiovascular and behavioral rule totals cannot reach Red with these bands; review remains scheduled. Physical sensor semantics, clinical validation, outbound notification delivery, and shared-host configuration are not implied by completing this prototype.
