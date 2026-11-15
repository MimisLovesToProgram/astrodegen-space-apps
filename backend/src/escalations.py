import json
from datetime import datetime, timezone
from pocketbase import PocketBase
from pocketbase.utils import ClientResponseError

# ============================================================
# CONFIGURATION
# ============================================================

POCKETBASE_URL = "http://127.0.0.1:8090"

SEVERITY_PRIORITY = {
    "red": 1,
    "orange": 2,
    "yellow": 3
}

DOMAIN_PRIORITY = {
    "cardiovascular": 1,
    "immune": 1,
    "bone_loss": 1,
    "behavioral": 2
}

VALID_DOMAINS = set(DOMAIN_PRIORITY.keys())


# ============================================================
# POCKETBASE ESCALATION SYSTEM
# ============================================================

class PocketBaseEscalationSystem:

    def __init__(self, base_url=POCKETBASE_URL):
        self.client = PocketBase(base_url)
        # Optional: Authenticate as admin or user if API rules require it
        # self.client.admins.auth_with_password("admin@example.com", "your_password")

    # --------------------------------------------------------
    # CREATE ACTION CARD
    # --------------------------------------------------------

    def generate_action_card(
        self,
        astronaut_id,
        domain,
        severity,
        recommended_action
    ):
        return {
            "astronaut_id": astronaut_id,
            "domain": domain,
            "severity": severity,
            "alert": True,
            "message": (
                f"{severity.upper()} alert detected "
                f"in the {domain} domain."
            ),
            "recommended_action": recommended_action,
            "status": "awaiting_acknowledgment"
        }

    # --------------------------------------------------------
    # UPDATE ASTRONAUT UI
    # --------------------------------------------------------

    def update_astronaut_ui(
        self,
        astronaut_id,
        domain,
        classification,
        action_card=None
    ):
        if classification == "green":
            return {
                "astronaut_id": astronaut_id,
                "domain": domain,
                "classification": "green",
                "message": "All good",
                "show_alert": False,
                "action_card": None
            }

        return {
            "astronaut_id": astronaut_id,
            "domain": domain,
            "classification": classification,
            "message": (
                f"{classification.upper()} alert: "
                f"{domain} risk detected."
            ),
            "show_alert": True,
            "action_card": action_card
        }

    # --------------------------------------------------------
    # CREATE OR UPDATE ESCALATION (Outbox Flow)
    # --------------------------------------------------------

    def create_escalation(
        self,
        astronaut_id,
        domain,
        severity,
        risk_score,
        action_card,
        sensor_readings,
        recipient="Flight Medical Team"
    ):
        domain = domain.lower()
        severity = severity.lower()

        if domain not in VALID_DOMAINS:
            raise ValueError(f"Unknown domain: {domain}")

        if severity not in SEVERITY_PRIORITY:
            raise ValueError(f"Invalid severity: {severity}")

        severity_priority = SEVERITY_PRIORITY[severity]
        domain_priority = DOMAIN_PRIORITY[domain]
        now = datetime.now(timezone.utc).isoformat()

        # Check if a pending escalation already exists for this astronaut and domain
        try:
            existing_records = self.client.collection("escalations").get_list(
                query_params={
                    "filter": f'astronaut_id="{astronaut_id}" && domain="{domain}" && status="pending"'
                }
            )

            if existing_records.items:
                existing = existing_records.items[0]
                escalation_id = existing.id

                # Update existing pending escalation while preserving flow
                self.client.collection("escalations").update(escalation_id, {
                    "severity": severity,
                    "risk_score": risk_score,
                    "severity_priority": severity_priority,
                    "domain_priority": domain_priority,
                    "action_card": action_card,
                    "sensor_readings": sensor_readings,
                    "recipient": recipient
                })
                return escalation_id

        except ClientResponseError as e:
            print(f"PocketBase query error: {e}")

        # Create new record in PocketBase
        payload = {
            "astronaut_id": astronaut_id,
            "domain": domain,
            "severity": severity,
            "risk_score": risk_score,
            "severity_priority": severity_priority,
            "domain_priority": domain_priority,
            "action_card": action_card,
            "sensor_readings": sensor_readings,
            "recipient": recipient,
            "status": "pending",
            "created_at": now
        }

        record = self.client.collection("escalations").create(payload)
        return record.id

    # --------------------------------------------------------
    # PROCESS ASSESSMENTS (Architecture Step 3 & 4)
    # --------------------------------------------------------

    def process_assessments(
        self,
        astronaut_id,
        assessments,
        sensor_readings
    ):
        ui_results = {}
        escalation_ids = []

        for domain in VALID_DOMAINS:
            if domain not in assessments:
                raise ValueError(f"Missing assessment for domain: {domain}")

            assessment = assessments[domain]
            risk_detected = assessment.get("risk_detected")
            classification = assessment.get("classification")

            if not isinstance(risk_detected, bool):
                raise ValueError(f"{domain}: risk_detected must be True or False")

            if classification not in ("green", "yellow", "orange", "red"):
                raise ValueError(f"{domain}: invalid classification")

            if not risk_detected and classification != "green":
                raise ValueError(f"{domain}: no risk must have green classification")

            if risk_detected and classification == "green":
                raise ValueError(f"{domain}: detected risk cannot be green")

            # Green status -> "All good" + trends (No escalation created)
            if not risk_detected:
                ui_results[domain] = self.update_astronaut_ui(
                    astronaut_id, domain, "green"
                )
                continue

            # Yellow / Orange / Red zone -> Action card + Escalation outbox
            recommended_action = assessment.get(
                "recommended_action",
                "Follow the approved mission protocol."
            )

            action_card = self.generate_action_card(
                astronaut_id,
                domain,
                classification,
                recommended_action
            )

            ui_results[domain] = self.update_astronaut_ui(
                astronaut_id,
                domain,
                classification,
                action_card
            )

            escalation_id = self.create_escalation(
                astronaut_id=astronaut_id,
                domain=domain,
                severity=classification,
                risk_score=assessment.get("risk_score"),
                action_card=action_card,
                sensor_readings=sensor_readings
            )

            escalation_ids.append(escalation_id)

        return {
            "astronaut_ui": ui_results,
            "escalation_ids": escalation_ids
        }

    # --------------------------------------------------------
    # GET PRIORITIZED ESCALATION QUEUE
    # --------------------------------------------------------

    def get_escalation_queue(self):
        records = self.client.collection("escalations").get_list(
            query_params={
                "filter": 'status="pending"',
                "sort": "severity_priority,domain_priority,created_at,id"
            }
        )
        return [record.__dict__ for record in records.items]

    # --------------------------------------------------------
    # ACKNOWLEDGE ESCALATION (Medical Personnel Action)
    # --------------------------------------------------------

    def acknowledge_escalation(
        self,
        escalation_id,
        acknowledged_by
    ):
        if not acknowledged_by:
            raise ValueError("acknowledged_by cannot be empty")

        acknowledged_at = datetime.now(timezone.utc).isoformat()

        try:
            record = self.client.collection("escalations").update(escalation_id, {
                "status": "acknowledged",
                "acknowledged_at": acknowledged_at,
                "acknowledged_by": acknowledged_by
            })
            return {
                "escalation_id": record.id,
                "status": "acknowledged",
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": acknowledged_at
            }
        except ClientResponseError:
            raise ValueError("Escalation not found or already acknowledged")


# ============================================================
# EXAMPLE INTEGRATION
# ============================================================

if __name__ == "__main__":
    system = PocketBaseEscalationSystem()
    astronaut_id = "AST-001"

    # Synthetic sensor readings mapped to your architecture domains
    sensor_readings = {
        "hr": 82,
        "hrv": 45,
        "spo2": 98,
        "temp": 36.8,
        "sleep": 7.5,
        "sleep_quality": 8,
        "exercise": 45,
        "mood": 7,
        "social_interaction": 6,
        "mission_day": 120,
        "symptoms": []
    }

    assessments = {
        "cardiovascular": {
            "risk_detected": True,
            "classification": "orange",
            "risk_score": 0.75,
            "recommended_action": "Review cardiovascular telemetry with medical team."
        },
        "immune": {
            "risk_detected": False,
            "classification": "green",
            "risk_score": 0.05
        },
        "bone_loss": {
            "risk_detected": True,
            "classification": "yellow",
            "risk_score": 0.40,
            "recommended_action": "Adjust resistance training parameters."
        },
        "behavioral": {
            "risk_detected": True,
            "classification": "red",
            "risk_score": 0.92,
            "recommended_action": "Immediate psychological support check-in."
        }
    }

    # Runs validation, UI updates, and pushes to PocketBase outbox queue if out of range
    results = system.process_assessments(astronaut_id, assessments, sensor_readings)
    print("Assessment Results Processed:", json.dumps(results, indent=4))