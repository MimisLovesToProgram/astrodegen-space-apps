# Astrocrates tasks and schedule

This board covers the non-UI implementation and its handoff to the frontend team. We distinguish working mechanisms from team decisions that are still needed. The mission and assessment policy are synthetic demonstrations.

| ID | Task | State | Remaining work or evidence |
| --- | --- | --- | --- |
| T01 | Agree official challenge requirements and demo scope | Pending team decision | Record the brief, source URL, and demo acceptance criteria |
| T02 | Supply synthetic sensor scenarios | Implemented | Three crew members, seven days, and a noise generator |
| T03 | Confirm real sensor semantics and time contract | Pending team decision | Confirm resting HR, RMSSD, units, sources, UTC clocks, cadence, and radiation semantics |
| T04 | Validate measurement schema, units, clocks, and plausibility | Implemented | Invalid inputs, conversions, and valid high HR are tested |
| T05 | Persist raw and clean data, duplicates, conflicts, and recovery | Implemented | Atomic packet processing and replay tests on SQLite and PocketBase |
| T06 | Connect simulator to storage and validation | Implemented with documented assumptions | 21 mission packets yield 252 unique clean observations |
| T07 | Supply clean history and a versioned assessment interface | Implemented | Configurable history, source filters, and handoff export |
| T08 | Agree assessment formulas and expected outcomes | Pending team decision | Team notes are now published; review their mapping, windows, freshness, sources, and unknown states; demo rules are not approval |
| T09 | Implement four-domain assessment calculations | Engine implemented; final policy pending T08 | Baselines, trends, consecutive rules, levels, and unknown states tested; fictional demo policy supplied |
| T10 | Persist results and retry failed assessments | Implemented | Frozen inputs/policy, leases, atomic completion, idempotency, failed-job retry and attempt limits |
| T11 | Connect capture, processing, assessment, and backend APIs | Backend implemented; frontend consumer pending | CLI connects all steps; authenticated login, profile, and full daily crew history are tested |
| T12 | Monitor data quality and escalation conditions | Prototype implemented | Missing/stale data, per-source gaps, durable quality recovery, and orange/red transitions tested; physical calibration and external notification delivery remain pending |
| T13 | Verify the demo and hand off to teammates | Backend verified; joint demo pending | Real PocketBase tests and local replay; frontend integration and final presentation rehearsal still needed |

## Team handoff tasks

| Task | State | Next action |
| --- | --- | --- |
| Crew login API | Implemented | Frontend sends username/password and retains the returned token |
| Sensor-history API | Implemented | Frontend sends crewId with token and handles levels 0–3 plus unknown `null` |
| Shared database setup | Local server configured | Agree the host and explicitly configure access from teammates' machines; managed setup remains localhost |
| UI integration | Pending frontend owner | Connect login, history, profile, and unknown-state rendering without embedding service credentials |
| Final scoring policy | Pending assessment owner | Review the newly published team notes, map them into the executable policy, and verify expected outcomes |
| External notifications | Pending if required by scope | Choose delivery channel and recipients before implementing outbound messages |
| Physical sensors | Pending if required by scope | Confirm devices, authenticity, calibration, and sampling policies |
| Repository cleanup | Partly complete | Canonical backend consolidated and runtime files untracked; review legacy challenge/idea folders with their owners before removing teammates' work |
| Official brief and presentation | Pending team decision | Agree scope and rehearse the integrated demo |

## Proposed next-session schedule

| Order | Work | Exit condition |
| --- | --- | --- |
| 1 | Confirm T01/T03/T08 and choose the shared host | Agreed scope, sensor semantics, scoring policy, and connection settings |
| 2 | Review and merge the backend feature branch through dev | Migrations and API contract reviewed; backend tests pass |
| 3 | Frontend owner connects crew endpoints | Login and history work with a real crew token; cross-crew access fails; unknown states are visible |
| 4 | Replace or approve the demo policy | Expected cases match the team's versioned rules |
| 5 | Run the full team demo and recovery checks | Capture → validation → assessment → UI works; retries do not duplicate results |

These are dependency-ordered tasks, not assigned calendar deadlines. Team owners still need to agree delivery dates.

## Verification

The full suite contains 91 tests, including isolated real-PocketBase servers, all three crew histories, permission boundaries, API response types, rate limiting, source filtering, job leases, retries, escalation deduplication, and backfills. It runs without changing the team's active database. The standard-library-only run skips PocketBase tests unless `POCKETBASE_TEST_BINARY` is set.

The original administrator, raw sensor deliveries, and validated observations are preserved during local setup. Generated binaries, databases, credentials, logs, and verification artifacts remain ignored. See the [assessment guide](assessment.md), [frontend API contract](frontend-api.md), and [backend setup](../backend/README.md). Frontend source was not changed by this implementation.

## New team specification

The latest team commit publishes `astronaut_health_monitoring_system_data.md` and data tables in `backend/src/health_data.py`. We must reconcile these with the executable policy before claiming the notes-based assessment is complete. The team file is preserved. Its `assesmentEngine.py` currently prints a startup message; the runnable implementation in this branch is `src/assessment/`. We should agree one entry point before retiring either path.

Specific decisions remain: daily streaks versus reading counts, a seven-day baseline with incomplete early history, elapsed time without social/exercise logs, activity percentage versus a boolean exercise log, and the yellow/red score boundaries (the notes define escalation thresholds but not all four score bands). The existing demo policy remains explicitly separate.
