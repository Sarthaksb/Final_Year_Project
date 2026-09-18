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
