"""PocketBase HTTP adapter; never opens or edits PocketBase's SQLite files."""

import json
import os
import uuid
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .adapters import sensor_observations
from .service import _raw_payload
from .validation import json_string, utc_string, validate_observation


class PocketBaseError(RuntimeError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(f"PocketBase HTTP {status}: {message}")


class PocketBaseTelemetry:
    def __init__(self, url="http://127.0.0.1:8090", token=None, timeout=15):
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("Provide an HTTP(S) PocketBase base URL without credentials, query, or fragment")
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def request(self, method, path, body=None, query=None):
        suffix = "?" + urlencode(query) if query else ""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = self.token
        request = Request(self.url + path + suffix,
                          data=json_string(body).encode() if body is not None else None,
                          headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
                return json.loads(payload) if payload else None
        except HTTPError as error:
            try:
                message = json.loads(error.read()).get("message", "Request failed")
            except (ValueError, AttributeError):
                message = "Request failed"
            raise PocketBaseError(error.code, message) from None

    def authenticate(self, email, password, collection="telemetry_services"):
        if collection not in ("telemetry_services", "_superusers"):
            raise ValueError("Unsupported auth collection")
        response = self.request("POST", f"/api/collections/{collection}/auth-with-password",
                                {"identity": email, "password": password})
        self.token = response["token"]
        return response["record"]

    @classmethod
    def from_environment(cls):
        client = cls(os.environ.get("POCKETBASE_URL", "http://127.0.0.1:8090"),
                     os.environ.get("POCKETBASE_TOKEN"))
        if not client.token:
            email, password = os.environ.get("POCKETBASE_EMAIL"), os.environ.get("POCKETBASE_PASSWORD")
            if not email or not password:
                raise ValueError("Set POCKETBASE_TOKEN or POCKETBASE_EMAIL and POCKETBASE_PASSWORD")
            client.authenticate(email, password)
        return client

    def capture(self, packet, *, delivery_key=None, assume_utc=False, reference_time=None):
        """Persist once per delivery key; reusing the key safely retries a timeout."""
        if not isinstance(assume_utc, bool):
            raise TypeError("assume_utc must be a boolean")
        payload, encoding = _raw_payload(packet)
        captured = packet.get("timestamp") if isinstance(packet, dict) else None
        body = {
            "delivery_key": delivery_key or uuid.uuid4().hex,
            "payload": payload, "payload_encoding": encoding,
            "captured_at": captured if isinstance(captured, str) else "",
            "assume_utc": assume_utc,
            "validation_time": utc_string(reference_time) if reference_time is not None else "",
        }
        for attempt in range(2):
            try:
                return self.request("POST", "/api/astrocrates/capture", body)
            except (URLError, TimeoutError):
                if attempt:
                    raise

    def validation_results(self, record):
        packet = json.loads(record["payload"]) if record["payload_encoding"] == "json" else record["payload"]
        clock = datetime.fromisoformat((record["validation_time"] or record["received_at"]).replace("Z", "+00:00"))
        results = []
        for raw in sensor_observations([packet], assume_utc=record["assume_utc"]):
            result = validate_observation(raw, clock)
            observation = result["observation"]
            if observation is not None:
                result["identity_key"] = json_string([
                    observation[key] for key in ("astronaut_id", "metric", "captured_at", "source")
                ])
                result["content_key"] = json_string([
                    observation[key] for key in ("unit", "value", "context")
                ])
            results.append(result)
        return results

    def process_pending(self, limit=100):
        """Read a bounded queue page; commit each packet's results atomically."""
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be an integer between 1 and 500")
        records = self.request("GET", "/api/collections/sensor_packets/records", query={
            "filter": 'status="pending"', "sort": "received_at,id", "perPage": limit, "skipTotal": "true",
        })["items"]
        summary = {"accepted": [], "quarantined": [], "duplicates": [], "conflicts": []}
        processed = []
        for record in records:
            result = self.request("POST", "/api/astrocrates/commit", {
                "packet_id": record["id"], "results": self.validation_results(record),
            })
            if not result["already_processed"]:
                processed.append(record["id"])
            for key in summary:
                summary[key].extend(result["ingestion"][key])
        return {"packet_ids": processed, "ingestion": summary}

    def get_history(self, astronaut_id, limit=250):
        """Read the same normalized observation contract used by local Step 3."""
        if not isinstance(astronaut_id, str) or not astronaut_id.strip():
            raise ValueError("astronaut_id is required")
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise ValueError("limit must be an integer between 1 and 10000")
        history = []
        page = 1
        page_size = min(limit, 500)
        while len(history) < limit:
            records = self.request("GET", "/api/collections/validated_observations/records", query={
                "filter": "astronaut_id=" + json_string(astronaut_id),
                "sort": "-captured_at,-id", "perPage": page_size, "page": page, "skipTotal": "true",
            })["items"]
            history.extend(record["observation"] for record in records)
            if len(records) < page_size:
                break
            page += 1
        return history[:limit]
