# Astrocrates frontend

This is the only Flutter application directory. We preserved the latest team screens and assets when removing the older challenge wrapper.

From this directory:

```bash
flutter pub get
flutter run --dart-define=ASTROCRATES_API_URL=http://127.0.0.1:8090
flutter analyze
flutter test
```

Use the URL of the agreed shared backend when it is available. `127.0.0.1` refers to the device running Flutter; a phone or emulator needs a reachable host address. The managed backend currently binds localhost. Release mobile builds should use HTTPS; the project does not globally enable cleartext networking.

Login uses the username/password endpoint and keeps the returned crew token in memory until sign-out. The app loads the user's profile and date-keyed history, displays unknown warnings explicitly, and submits check-ins with named symptoms and an activity percentage. Check-in reminders are local and scoped to the signed-in crew. They are updated only after the server accepts the raw check-in.

Check-ins enter the durable raw queue. Run the documented Python worker to validate and assess them; the frontend reports that processing may still be pending and offers Refresh. We never package backend service-account credentials into the app.

See [the API contract](../../docs/frontend-api.md) and [team assessment policy](../../docs/assessment.md).

To run the real client/backend integration from the repository root:

```bash
POCKETBASE_TEST_BINARY="$PWD/backend/pocketbase" FLUTTER_TEST_BINARY="$(command -v flutter)" PYTHONPATH=src:tests python3 tests/run_frontend_integration.py
```

This creates temporary accounts and data, runs the Dart client with a live validation/assessment worker, and stops the test server afterward. It does not modify the active database. The standard `flutter test` run skips this live case unless its private test connection settings are supplied by the harness.

Verified with Flutter 3.50 / Dart 3.14. We use the official standalone `material_ui` package, following [Flutter's migration guide](https://docs.flutter.dev/release/breaking-changes/material-ui-and-cupertino-ui).
