"""
triage/scoring.py
-----------------
Rule-based triage scoring function.

Combines model confidence + red-flag symptoms + malignancy score into a
single urgency label:

    HIGH   — any red-flag symptom is present (bleeding, rapid_growth,
              irregular_border, OR the itching+pain combo), regardless of
              confidence.  Clinically dangerous symptoms always escalate.

    MEDIUM — no red flag AND any of:
              * confidence < 0.60
              * predicted class is in {MEL, SCC}
              * malignancy_score (P(MEL)+P(BCC)+P(SCC)) >= 0.30
              * P(MEL) >= 0.20 OR P(SCC) >= 0.20

    LOW    — all conditions above clear.  Always appended with the
              disclaimer: "Monitor and consult a doctor if it changes."


    HIGH   — any red-flag symptom is present (bleeding, rapid_growth,
              irregular_border, OR the itching+pain combo), regardless of
              confidence.  Clinically dangerous symptoms always escalate.

    MEDIUM — no red flag AND (confidence < 0.60 OR predicted class is in the
              high-risk set {MEL, SCC}).  Either the model is uncertain, or
              the prediction itself is a malignant class that warrants prompt
              review even when the model is confident.

    LOW    — no red flag AND confidence >= 0.60 AND class is not high-risk.
              The model is confident and the predicted lesion is lower-risk.

The red-flag definitions are imported directly from agent/config.py so the
triage scorer and the LangGraph orchestrator always share the same thresholds.

Usage
-----
    from triage.scoring import compute_urgency, TriageResult

    result = compute_urgency(
        confidence=0.72,
        predicted_class="MEL",
        symptoms={"bleeding": False, "rapid_growth": False},
    )
    print(result.urgency)       # "MEDIUM"
    print(result.reasons)       # ["High-risk class: MEL (confidence 72%)"]
    print(result.score)         # 5  (numeric, for sorting / dashboards)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

# ── Import shared red-flag constants from the agent orchestrator ──────────────
# This keeps a single source of truth for symptom definitions across the system.
import sys
import os

# Allow import whether called from project root or as a module
_project_root = os.path.join(os.path.dirname(__file__), "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from agent.config import (
    CONFIDENCE_THRESHOLD,
    RED_FLAG_SYMPTOMS,
    URGENT_COMBO,
    MALIGNANCY_SCORE_MEDIUM,
    HIGH_RISK_PROB_MEDIUM,
    LOW_URGENCY_DISCLAIMER,
)

# ── High-risk class set (explicit list — no ML, no model call) ────────────────
# MEL = Melanoma, SCC = Squamous Cell Carcinoma: both are malignant and warrant
# prompt clinical review even when the model prediction is confident.
HIGH_RISK_CLASSES: frozenset[str] = frozenset({"MEL", "SCC"})

# ── Numeric score mapping (useful for sorting on dashboards) ──────────────────
_URGENCY_SCORE: dict[str, int] = {
    "HIGH":   10,
    "MEDIUM":  5,
    "LOW":     1,
}


# ── Return type ───────────────────────────────────────────────────────────────

@dataclass
class TriageResult:
    """
    Attributes
    ----------
    urgency : str
        One of "HIGH" | "MEDIUM" | "LOW".
    score : int
        Numeric representation: HIGH=10, MEDIUM=5, LOW=1.
        Useful for sorting or threshold comparisons on a dashboard.
    reasons : list[str]
        Human-readable list of the specific rules that fired.
        Always at least one entry.
    confidence : float
        Echo of the input confidence, for convenience.
    predicted_class : str
        Echo of the input class.
    """
    urgency: str
    score: int
    reasons: list[str]
    confidence: float
    predicted_class: str


# ── Core scoring function ─────────────────────────────────────────────────────

def compute_urgency(
    confidence: float,
    predicted_class: str,
    symptoms: dict[str, bool],
    all_probabilities: dict[str, float] | None = None,
    is_lesion_changed: bool = False,
) -> TriageResult:
    """
    Compute a triage urgency label from model outputs + symptom answers.

    Parameters
    ----------
    confidence : float
        Softmax probability of the top-1 prediction (0.0 – 1.0).
    predicted_class : str
        Model's top-1 class label, e.g. "MEL", "NV", "BCC".
    symptoms : dict[str, bool]
        Symptom questionnaire answers.  Any key not present defaults to False.
        Recognised keys: rapid_growth, bleeding, irregular_border,
                         itching, pain (others are ignored, not error).
    all_probabilities : dict[str, float] | None
        Full 8-class softmax distribution from the model.  Used to compute
        the malignancy score P(MEL)+P(BCC)+P(SCC).  If None, the score
        defaults to 0.0 (safe fallback — class-name rules still apply).
    is_lesion_changed : bool
        If True, the lesion has tracked changes (e.g. malignancy score rose
        by >= 0.15). Forces urgency to at least MEDIUM.

    Returns
    -------
    TriageResult
    """
    reasons: list[str] = []

    # ── Rule 1: check individual red-flag symptoms ────────────────────────────
    triggered_flags: list[str] = [
        sym for sym in RED_FLAG_SYMPTOMS if symptoms.get(sym, False)
    ]
    if triggered_flags:
        reasons.append(
            f"Red-flag symptom(s) present: {', '.join(triggered_flags)}"
        )

    # ── Rule 2: check itching + pain combo ───────────────────────────────────
    combo_a, combo_b = URGENT_COMBO
    if symptoms.get(combo_a, False) and symptoms.get(combo_b, False):
        combo_label = f"{combo_a}+{combo_b} combination"
        if combo_label not in reasons:          # avoid double-listing
            reasons.append(f"Red-flag combo: {combo_label}")

    # ── Any red flag → HIGH, stop here ───────────────────────────────────────
    if reasons:
        return TriageResult(
            urgency="HIGH",
            score=_URGENCY_SCORE["HIGH"],
            reasons=reasons,
            confidence=confidence,
            predicted_class=predicted_class,
        )

    # ── No red flag: check MEDIUM conditions ─────────────────────────────────
    medium_reasons: list[str] = []

    if confidence < CONFIDENCE_THRESHOLD:
        medium_reasons.append(
            f"Low model confidence ({confidence:.0%} < {CONFIDENCE_THRESHOLD:.0%} threshold)"
        )

    if predicted_class.upper() in HIGH_RISK_CLASSES:
        medium_reasons.append(
            f"High-risk class: {predicted_class.upper()} (confidence {confidence:.0%})"
        )

    if is_lesion_changed:
        medium_reasons.append("Lesion malignancy score increased by >= 0.15 since last review.")

    # ── Malignancy score rules (use all_probabilities when available) ────────
    _p = all_probabilities or {}
    mel_prob = float(_p.get("MEL", 0.0))
    bcc_prob = float(_p.get("BCC", 0.0))
    scc_prob = float(_p.get("SCC", 0.0))
    malignancy_score = mel_prob + bcc_prob + scc_prob

    if malignancy_score >= MALIGNANCY_SCORE_MEDIUM:
        reason = (
            f"Malignancy score {malignancy_score:.2f} >= {MALIGNANCY_SCORE_MEDIUM} "
            f"(P(MEL)={mel_prob:.2f}, P(BCC)={bcc_prob:.2f}, P(SCC)={scc_prob:.2f})"
        )
        if reason not in medium_reasons:
            medium_reasons.append(reason)

    if mel_prob >= HIGH_RISK_PROB_MEDIUM:
        reason = f"P(MEL)={mel_prob:.2f} >= {HIGH_RISK_PROB_MEDIUM} threshold"
        if reason not in medium_reasons:
            medium_reasons.append(reason)

    if scc_prob >= HIGH_RISK_PROB_MEDIUM:
        reason = f"P(SCC)={scc_prob:.2f} >= {HIGH_RISK_PROB_MEDIUM} threshold"
        if reason not in medium_reasons:
            medium_reasons.append(reason)

    if medium_reasons:
        return TriageResult(
            urgency="MEDIUM",
            score=_URGENCY_SCORE["MEDIUM"],
            reasons=medium_reasons,
            confidence=confidence,
            predicted_class=predicted_class,
        )

    # ── Fallthrough → LOW ─────────────────────────────────────────────────────
    return TriageResult(
        urgency="LOW",
        score=_URGENCY_SCORE["LOW"],
        reasons=[
            f"No red-flag symptoms; {predicted_class.upper()} predicted "
            f"with {confidence:.0%} confidence (>= {CONFIDENCE_THRESHOLD:.0%} threshold)",
            LOW_URGENCY_DISCLAIMER,   # safety rule: always present on LOW
        ],
        confidence=confidence,
        predicted_class=predicted_class,
    )
