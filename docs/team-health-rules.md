# Astronaut Health Monitoring & Escalation System

## 1. Biometric & Behavioral Telemetry Thresholds
*Note: The variables from `sleep_h` to `social_interaction` are marked as **user**-logged inputs, while preceding metrics represent automated sensor telemetry. Collectively, this serves as the **starting set for validation**.*

| Variable | Input Type | Normal Range | Watch | Alert |
| :--- | :--- | :--- | :--- | :--- |
| `hr (resting)` | Sensor | $50\text{--}100\text{ bpm}$ | $100\text{--}110$ or $45\text{--}50\text{ bpm}$ | $> 120$ or $< 45\text{ bpm}$ |
| `hrv` | Sensor | $40\text{--}80\text{ ms}$ | $30\text{--}40\text{ ms}$ | $< 30\text{ ms}$ |
| `spo2` | Sensor | $95\text{--}100\%$ | $92\text{--}95\%$ | $< 92\%$ |
| `temp_c` | Sensor | $36.0\text{--}37.5^\circ\text{C}$ | $37.5\text{--}38.5^\circ\text{C}$ | $\ge 38.6^\circ\text{C}$ or $< 35.5^\circ\text{C}$ |
| `radiation_msv_cumulative` | Sensor | $< 600\text{ mSv}$ | $60\%\text{ of limit}$ | $\ge \text{limit}$ |
| `sleep_h` | User | $7\text{--}9\text{ h}$ | $6\text{--}7\text{ h}$ | $< 6\text{ h}$ |
| `sleep_quality` | User | $3\text{--}5$ | $2$ | $1$ |
| `mood` | User | $3\text{--}5$ | $2$ | $1$ |
| `symptoms` | User | `empty` | $1\text{ symptom}$ | $\ge 2\text{ symptoms}$ |
| `exercise_logged` | User | `true` most days | $3+\text{ days false}$ | $3+\text{ days false}$ |
| `social_interaction` | User | `true` most days | $2\text{ days false}$ | $3+\text{ days false}$ |

---

## 2. Physiological Domains & Spaceflight Rationale

### Domain Mappings
* **Immune:** `sleep`, `sleep_quality`, `temp`, `spo2`, `symptoms`
* **Cardiovascular:** `hr`, `hrv`, `exercise`, `spo2`
* **Behavioral:** `mood`, `sleep_quality`, `social_interaction`, `sleep_h`
* **Bone Loss:** `exercise_logged`, `mission_day`

### Why It Matters (Spaceflight Impact)
* **Immune:** Space radiation, sleep debt, and stress suppress immune function.
* **Cardiovascular:** Microgravity deconditions the heart and causes fluid shifts.
* **Behavioral:** Isolation causes sleep disruption and mood decline.
* **Bone Loss:** Astronauts experience $1\text{--}1.5\%$ bone loss per month in weight-bearing bones without countermeasures.

---

## 3. Risk Assessment Models (0–100 Scale)

### Immune Risk
* **+30 points:** If `sleep` $< 6\text{ h}$ for $3+$ days
* **+25 points:** If `spo2` $< 95\%$
* **+20 points:** If `temp` $> 37.5^\circ\text{C}$
* **+15 points:** If symptom `"sore throat"` or `"fatigue"` is checked
* **+10 points:** If `hrv` dropped $> 20\%$ vs. 7-day baseline
* **Trigger ($\ge 60$):** `"Elevated - rest, hydrate, notify personnel"`

### Bone Loss Risk
* **+2 points:** Per mission day without resistance exercise log
* **+20 points:** If $> 14$ days since last exercise session
* **Trigger ($\ge 50$):** `"Run bone density protocol, mandatory resistance session today"`

### Cardiovascular Risk
* **+25 points:** If resting `hr` $>$ baseline $+ 15\text{ bpm}$ for 2 days
* **+20 points:** If `hrv` $<$ baseline $- 25\%$
* **+15 points:** If activity $< 50\%$ of target
* **Trigger ($\ge 55$):** `"Cardio deconditioning - schedule exercise log for ground review"`

### Behavioral Risk
* **+20 points:** If `mood` $\le 2$ for $2+$ days
* **+20 points:** If `sleep_quality` $\le 2$
* **+15 points:** If no `social_interaction` logged in $48\text{ h}$
* **Trigger ($\ge 50$):** `"Check in with crew, schedule ground call, log mood journal"`

---

## 4. Data Pipeline & Escalation Architecture

### Processing Pipeline
1. **Sensors / User Input:** Raw biometric and self-reported data collection.
2. **Ingest + Validate:**
   1. Check each field against normal ranges.
   2. Detect streaks and trends vs. rolling baseline.
   3. Aggregate metrics into per-domain status.
   4. Emit an escalation when a domain hits **Orange**.
3. **Assess vs. Normal Range:** Evaluate state and route accordingly:
   * **In Range (Green):**
     * **Astronaut UI:** Display `"all good"` + positive health trends.
   * **Out of Range (Yellow / Orange / Red):**
     * **Astronaut UI:** Display alert + recommended action card.
     * **Escalation Creation:** Route to the **Escalation Queue** (the outbox).
     * **Medical Review:** Sent to **Ground / Flight Medical Personnel**.
     * **Resolution:** Personnel review updates status $\rightarrow$ `Acknowledged`.

### Escalation Queue Prioritization
1. **Severity First:** `Red` $\rightarrow$ `Orange` $\rightarrow$ `Yellow`
2. **Domain Priority:** `Cardiovascular` / `Immune` ahead of `Behavioral` *(adjustable)*