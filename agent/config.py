"""
agent/config.py
---------------
Centralised configuration for the orchestrator agent.
All threshold values and red-flag definitions live here so they can be
changed in one place without touching graph or node logic.
"""

# ── Confidence threshold ──────────────────────────────────────────────────────
# Predictions below this value are considered uncertain; the agent triggers
# the Follow-Up branch (unless red flags are present — those always win).
CONFIDENCE_THRESHOLD: float = 0.60

# ── OOD (Out-Of-Distribution) gate ────────────────────────────────────────────
# Max-softmax below this → reject as non-skin image (status: invalid_image).
OOD_MAX_SOFTMAX_THRESHOLD: float = 0.30
# Energy-score above this (less negative) → additional OOD signal.
OOD_ENERGY_THRESHOLD: float = -5.0

# ── Temperature scaling ───────────────────────────────────────────────────────
# Filename (relative to ml/classifier/) where the fitted temperature is stored.
TEMPERATURE_JSON: str = "temperature.json"
# Filename (relative to ml/classifier/) where OOD val-set stats are stored.
OOD_STATS_JSON: str = "ood_stats.json"

# ── Malignancy score thresholds ───────────────────────────────────────────────
# malignancy_score = P(MEL) + P(BCC) + P(SCC)
# If >= this value, urgency is at least MEDIUM.
MALIGNANCY_SCORE_MEDIUM: float = 0.30
# If P(MEL) >= this OR P(SCC) >= this, urgency is at least MEDIUM.
HIGH_RISK_PROB_MEDIUM: float = 0.20

# ── LOW urgency disclaimer (safety rule) ──────────────────────────────────────
# Every LOW result MUST append this message.
LOW_URGENCY_DISCLAIMER: str = (
    "Monitor and consult a doctor if it changes."
)

# ── Red-flag individual symptoms ──────────────────────────────────────────────
# Any single symptom in this set immediately routes the case to URGENT,
# regardless of model confidence.
RED_FLAG_SYMPTOMS: set[str] = {
    "rapid_growth",
    "bleeding",
    "irregular_border",
}

# ── Red-flag combination ──────────────────────────────────────────────────────
# Both symptoms in this pair must be True simultaneously to trigger URGENT.
URGENT_COMBO: tuple[str, str] = ("itching", "pain")

# ── Branch name constants ─────────────────────────────────────────────────────
BRANCH_URGENT: str = "urgent"
BRANCH_FOLLOWUP: str = "followup"
BRANCH_NORMAL: str = "normal"
