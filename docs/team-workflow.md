# Team workflow

## Repository access

The repository owner can invite members through GitHub repository Settings → Collaborators. Team members must accept their invitations before pushing changes.

## Working on a change

1. Update your local `main`: `git switch main` followed by `git pull --ff-only`.
2. Create a branch, for example `git switch -c health-monitoring/initial-design`.
3. Keep changes in the relevant challenge folder. Put common resources in `shared/` only when multiple challenges use them.
4. Commit and push your branch, then open a pull request targeting `main`.
5. Ask another member to review the change before merging. Run relevant checks once code and tests exist.

Suggested branch names: `health-monitoring/<task>`, `<other-challenge>/<task>`, and `docs/<topic>`.

## Switching challenges

Add a new folder under `challenges/`, update the root README, and record the reason in `docs/decisions.md`. Keep earlier work available for reference.
