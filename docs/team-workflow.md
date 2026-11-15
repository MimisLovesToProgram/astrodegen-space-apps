# Team workflow

Use English for project documentation, comments, interface text, and commits. Describe implemented behavior separately from planned work.

Create a feature branch from an up-to-date `dev`, keep each commit focused, and open a pull request targeting `dev` when the work is ready for review. Suggested branch names are `sensors/<task>`, `ingestion/<task>`, `assessment/<task>`, `frontend/<task>`, and `docs/<task>`.

Keep the Flutter application in `src/app_frontend/`, Python code in `src/`, backend configuration in `backend/`, tests in `tests/`, and architecture and plans in `docs/`. Create new folders only when there is content for them. Keep generated databases, runtime binaries, credentials, and private data out of Git. Document external data sources and usage rights alongside the relevant work.

Run `PYTHONPATH=src python3 -m unittest discover -s tests -v` for Python changes. Use the existing Flutter checks for frontend changes. Team members must accept repository invitations before pushing branches.
