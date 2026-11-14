# Non-UI task plan and schedule

This plan excludes the existing Flutter UI and UI redesign. It covers the sensor contract, ingestion, health assessment, backend delivery, and verification. Owners and a calendar deadline have not been assigned; the schedule uses working days relative to the team's next development session. Estimates are provisional.

## Task board

| ID | Task | Current state | Depends on | Completion evidence |
| --- | --- | --- | --- | --- |
| T01 | Record official challenge requirements and demo scope | Pending | Team decision | Brief, source URL, and agreed demo acceptance criteria |
| T02 | Supply synthetic sensor scenarios | Implemented | — | Existing three-crew, seven-day story and noise generator |
| T03 | Confirm sensor semantics and time contract | Pending | T02 | Confirm resting HR, HRV method, units, source IDs, UTC timestamps, cumulative radiation semantics |
| T04 | Validate schema, units, timestamps, and plausibility | Implemented | — | Tests include invalid inputs, conversions, and valid high HR |
| T05 | Persist raw and validated records; handle retransmissions | Implemented | T04 | SQLite audit, duplicates, conflicts, history, and rollback tests |
| T06 | Connect the existing simulator to ingestion | Implemented with documented assumptions | T02, T04, T05 | 21 synthetic packets produce 252 accepted observations; repeat produces duplicates |
| T07 | Define clean-history assessment interface | Implemented | T05, T06 | Assessor callback receives validated crew history; invalid measurements stay out |
| T08 | Agree assessment formulas, baselines, windows, and missing-data behavior | Pending | T01, T03, T07 | Versioned assessment specification with units and expected synthetic cases |
| T09 | Implement physiological, behavioral, immune, and bone assessment calculations | Pending | T08 | Deterministic unit tests against the agreed formulas; no medical claims beyond the prototype |
| T10 | Persist assessment results and support failed-assessment retry | Pending | T09 | Versioned results linked to input history; retry works without re-ingesting duplicate measurements |
| T11 | Add bounded live ingestion and backend transport | Pending | T03, T07, T10 | Finite batches, explicit delivery contract, query/assessment API or agreed file interface |
| T12 | Add data-quality monitoring | Pending | T03, T05 | Missing/stale data reports, quality summaries, sensor reliability rules agreed with team |
| T13 | Verify the complete non-UI demo and handoff | Partly implemented | T09, T10, T11, T12 | Full sensor -> validation -> assessment run, replay/failure tests, setup and demo instructions |

T09 requires agreed formulas before implementation. A physiological change can be a valid observation and still matter to assessment; baseline deviations must not silently remove those observations from Step 3. The current adapter and assessment hook do not mean T09 is complete.

## Proposed working-day schedule

| Working day | Work | Dependency and exit condition |
| --- | --- | --- |
| Day 1 | Review current Step 1/2 connection; finish T01 and T03 | Team confirms requirements and sensor meaning; run the synthetic demo and tests |
| Day 2 | Complete T08; define expected stable/change/missing-data cases | Assessment owner signs off on formulas, history windows, and output contract |
| Days 3–4 | Implement T09 and T10 | Formula tests pass; assessment results are persisted and failures can be retried |
| Day 5 | Implement T11 | Bounded delivery connects ingestion to the implemented assessor; backend transport is documented |
| Day 6 | Implement T12 and finish T13 | Full non-UI replay passes, invalid data stays out of scoring, failures are recoverable |

Use one responsible owner per pending task when the team assigns work. T01 and T03 can be discussed together; T09 cannot be reliably estimated until T08 is agreed. If the deadline is shorter, prioritize one agreed assessment path through T09–T11 and schedule the remaining domains explicitly rather than marking them complete.

## Current verification checkpoint

The repository includes automated validation/storage tests and integration tests using the actual simulator functions. The connected synthetic mission covers all three crew members and all twelve emitted metrics, including symptoms and mission day. Callback tests verify the Step 3 contract; they are not tests of a health-risk engine. No UI changes are part of this plan.
