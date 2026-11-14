# Astrocrates non-UI task plan and schedule

This plan excludes the existing Flutter UI and UI redesign. It covers the sensor contract, ingestion, health assessment, backend delivery, and verification. Owners and a calendar deadline have not been assigned; the schedule uses working days relative to the team's next development session. Estimates are provisional.

## Task board

| ID | Task | Current state | Depends on | Completion evidence |
| --- | --- | --- | --- | --- |
| T01 | Record official challenge requirements and demo scope | Pending | Team decision | Brief, source URL, and agreed demo acceptance criteria |
| T02 | Supply synthetic sensor scenarios | Implemented | — | Existing three-crew, seven-day story and noise generator |
| T03 | Confirm sensor semantics and time contract | Pending | T02 | Confirm resting HR, HRV method, units, source IDs, UTC timestamps, cumulative radiation semantics |
| T04 | Validate schema, units, timestamps, and plausibility | Implemented | — | Tests include invalid inputs, conversions, and valid high HR |
| T05 | Persist raw and validated records; handle retransmissions | Implemented | T04 | Durable raw inbox, linked metric audit, clean history, duplicates/conflicts, and rollback tests on SQLite and PocketBase |
| T06 | Connect the existing simulator to ingestion | Implemented with documented assumptions | T02, T04, T05 | 21 synthetic packets produce 252 accepted observations; repeat produces duplicates |
| T07 | Define clean-history assessment interface | Implemented | T05, T06 | Assessor callback receives validated crew history; invalid measurements stay out |
| T08 | Agree assessment formulas, baselines, windows, and missing-data behavior | Pending | T01, T03, T07 | Versioned assessment specification with units and expected synthetic cases |
| T09 | Implement physiological, behavioral, immune, and bone assessment calculations | Pending | T08 | Deterministic unit tests against the agreed formulas; no medical claims beyond the prototype |
| T10 | Persist assessment results and support failed-assessment retry | Pending | T09 | Versioned results linked to input history; retry works without re-ingesting duplicate measurements |
| T11 | Add bounded live ingestion and backend transport | Capture, worker, and history API implemented; assessment delivery pending | T03, T07, T10 | PocketBase APIs and SQLite offline commands are tested; connect the real assessor once T09/T10 exist |
| T12 | Add data-quality monitoring | Pending | T03, T05 | Missing/stale data reports, quality summaries, sensor reliability rules agreed with team |
| T13 | Verify the complete non-UI demo and handoff | Partly implemented | T09, T10, T11, T12 | Full sensor -> validation -> assessment run, replay/failure tests, setup and demo instructions |

T09 requires agreed formulas before implementation. A physiological change can be a valid observation and still matter to assessment; baseline deviations must not silently remove those observations from Step 3. The current adapter and assessment hook do not mean T09 is complete.

## Proposed working-day schedule

| Working day | Work | Dependency and exit condition |
| --- | --- | --- |
| Day 1 | Review current Step 1/2 connection; finish T01 and T03 | Team confirms requirements and sensor meaning; run the synthetic demo and tests |
| Day 2 | Complete T08; define expected stable/change/missing-data cases | Assessment owner signs off on formulas, history windows, and output contract |
| Days 3–4 | Implement T09 and T10 | Formula tests pass; assessment results are persisted and failures can be retried |
| Day 5 | Finish the assessment portion of T11 | Existing capture/worker/history APIs connect to the implemented assessor; test durable assessment retries |
| Day 6 | Implement T12 and finish T13 | Full non-UI replay passes, invalid data stays out of scoring, failures are recoverable |

Use one responsible owner per pending task when the team assigns work. T01 and T03 can be discussed together; T09 cannot be reliably estimated until T08 is agreed. If the deadline is shorter, prioritize one agreed assessment path through T09–T11 and schedule the remaining domains explicitly rather than marking them complete.

## Current verification checkpoint

The repository includes automated validation/storage tests and integration tests using the actual simulator functions. The connected synthetic mission covers all three crew members and all twelve emitted metrics, including symptoms and mission day. Callback tests verify the Step 3 contract; they are not tests of a health-risk engine. No UI changes are part of this plan.

## Folder and backend checkpoint

The project now uses a single Astrocrates layout: `frontend/`, `src/`, `backend/pocketbase/`, `tests/`, and `docs/`. Step 1 saves timestamped packets before validation. Step 2 uses bounded, recoverable processing with atomic results and completion markers. Shared PocketBase APIs and offline SQLite use the same clean observation contract. The original simulator and Flutter source are preserved. Risk calculations and UI integration are still pending.

## Step 2 handoff checklist

The Step 2 implementation is complete for the synthetic prototype. Validation, unit conversion, raw capture, clean storage, duplicate/conflict handling, recovery, APIs, and the Step 3 data interface are implemented. All 37 tests pass with the installed PocketBase v0.42.2.

The remaining work for the Step 2 owner is:

- [ ] Confirm the sensor contract with the Step 1 owner: resting HR, HRV method, units, source identifiers, timestamp policy, and sampling frequency (T03).
- [ ] Start PocketBase from `backend/pocketbase/` so the committed migrations are applied to the actual local database.
- [ ] Configure ingest/worker/reader service accounts and environment settings for the local demo.
- [ ] Run capture -> process -> history on the actual local backend and check the records in its dashboard; existing integration tests use temporary databases.
- [ ] Agree the history window and hand off the normalized observation contract to the Step 3 owner (T08).
- [ ] Connect the real assessment engine when T09 is available, then verify failure and retry behavior (T10/T11/T13).

Missing/stale-data monitoring, sensor reliability scoring, and quality summaries (T12) are additional work. Risk formulas, baseline assessment calculations, and persistent risk results are not implemented and belong to Step 3. The existing UI is outside this owner's implementation scope; live UI/backend integration is still pending.
