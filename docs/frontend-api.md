# Crew API handoff

The local base URL is `http://127.0.0.1:8090`. The managed setup currently binds to localhost. Another laptop cannot use that address to reach this machine. A shared host address and network access must be configured before the team can use one server across laptops.

## Login

`POST /api/astrocrates/login`, with `Content-Type: application/json`:

```json
{"username":"crew_a","password":"YOUR_PRIVATE_PASSWORD"}
```

Successful authentication returns HTTP 200:

```json
{"crewId":"a","token":"POCKETBASE_USER_TOKEN"}
```

Invalid credentials return HTTP 200 with `{"crewId":""}`. Excessive attempts return HTTP 429 with `Retry-After`. We respect the collection authentication rule and refuse this password-only adapter when MFA is enabled. Do not attach a stale authorization token to login requests.

Use the returned token as `Authorization: Bearer POCKETBASE_USER_TOKEN` on crew routes. A crew ID alone grants no access. Backend ingest/worker/reader accounts are separate from crew logins.

## Sensor history

`POST /api/astrocrates/sensors`, with the authorization header and JSON:

```json
{"crewId":"a"}
```

Example response shape:

```json
{
  "2026-11-14": {
    "sleep_h": [5.8, 1],
    "sleep_q": [4, 0],
    "social_interactions": [true, 0],
    "mission_day": [1, null]
  }
}
```

This illustrates the contract, not a particular stored assessment. Each metric contains `[value, warningLevel]`. Levels 0–3 mean green, yellow, orange, and red. `null` means unassessed or unavailable, and the UI must show an unknown state. It must never convert `null` to green. Some metrics have no demo scoring rule; early days can also lack sufficient baseline data.

We return every stored UTC day, selecting the latest validated observation for each metric that day. This daily response intentionally aggregates intraday history; service history APIs retain the individual observations. Ties use a deterministic source/record order. A warning is attached only when the assessment used that exact timestamp and source. A newer unassessed reading does not inherit an older warning.

Canonical ingestion names remain in the database. The response aliases `hrv_rmssd` to `hrv`, `sleep_quality` to `sleep_q`, and `social_interaction` to `social_interactions`. Other field names stay canonical, including `hr_resting`, `spo2`, `temp_c`, `sleep_h`, `mood`, `symptoms`, `exercise_logged`, `radiation_msv_cumulative`, and `mission_day`. Values retain their JSON number, boolean, or list type.

No history returns `{}`. Missing/invalid authentication returns HTTP 401; another crew member's ID returns HTTP 403. Response headers include `X-Assessment-Status`, `X-Assessment-Mode`, and `X-Unknown-Metrics`. The demo mode is `synthetic_demo`. Set `ASTROCRATES_POLICY_ID` on the server to restrict displayed assessments to a particular policy if multiple policies are used.

## Profile and local demo users

`GET /api/astrocrates/me` returns `crewId`, `name`, and current `status` for the authenticated user. We keep profile fields out of the date-keyed sensors response.

Run setup with `--seed-demo-users` to provision the three synthetic crew accounts. Private credentials are saved to ignored `.env.crew-a`, `.env.crew-b`, and `.env.crew-c`, with owner-only permissions. Existing accounts are checked rather than having their passwords reset. Do not commit or paste these files into frontend source.

The canonical Flutter app now calls these endpoints, keeps the token in memory, displays unknown states, and scopes check-in dates per crew. A joint device/network rehearsal still needs to be completed.

## Submit a check-in

`POST /api/astrocrates/checkin` requires the crew user token. Example body:

```json
{
  "crewId": "a",
  "deliveryKey": "stable-random-key-12345",
  "values": {
    "sleep_h": 5.5,
    "sleep_quality": 2,
    "mood": 2,
    "symptoms": ["fatigue"],
    "exercise_logged": false,
    "social_interaction": true,
    "activity_pct_target": 40
  }
}
```

The server returns HTTP 202 with the raw packet ID, processing status, and replay flag. We derive the crew from the authenticated account and timestamp the submission on the server. The same delivery key and answers reuse the original packet; changed answers with the same key return HTTP 409. Cross-crew submissions return HTTP 403. Invalid answer types/ranges return HTTP 400. Symptom values are names, not a count; `exercise_logged` and `social_interaction` are booleans, and activity is a percentage, independent of exercise completion.

The worker normalizes these packets with source `crew_checkin` and `context.simulated=false`. Synthetic packets retain source `synthetic_biosensors`. A failed response can be retried with the same delivery key. Success means the original answers are durable, not that validation and scoring have already completed.
