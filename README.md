# ASTRODEGEN — Space Apps

Team workspace for NASA Space Apps Challenge preparation, challenge exploration, and prototypes.

## Structure

```text
challenges/
  health-monitoring/   # ASTRA: sensor simulator, ingestion, and Flutter prototype
ideas/                # Alternative challenge ideas and comparisons
shared/               # Resources used by multiple challenges
docs/                 # Team workflow and project decisions
```

Our current focus is **ASTRA — astronaut health monitoring**. This is a preliminary project idea; an official challenge statement and requirements have not yet been recorded here.

## Adding or changing a challenge

Create a new folder at `challenges/<challenge-name>/` with its own README, source, documentation, and tests as needed. Keep existing challenge folders so their work remains available. Record the selected challenge and the reason for switching in `docs/decisions.md`, and update the current focus above.

Use `ideas/README.md` to compare options before starting another prototype.

## Team collaboration

See [the team workflow](docs/team-workflow.md). Team members need repository access before they can push branches. Use branches and pull requests for implementation work.

The health-monitoring prototype contains a synthetic sensor generator, a tested Python ingestion and validation pipeline with SQLite storage, and a Flutter interface prototype. Health-risk assessment is still pending. See the [challenge guide](challenges/health-monitoring/README.md) for commands and the [non-UI task schedule](challenges/health-monitoring/docs/task-plan.md) for remaining work.
