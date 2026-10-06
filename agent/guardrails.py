"""
agent/guardrails.py
-------------------
Pure-Python post-generation guardrail for all Gemini branch nodes.

Rules (in order):
  1. Urgency field in result must match the triage urgency passed in.
     (LLM is NEVER allowed to override urgency — only triage/scoring.py does.)
  2. Response must not contain any forbidden phrase (e.g. "no cancer",
     "you are fine", "you don't have cancer", "no need to see a doctor").

If either rule is violated, the result dict is replaced by a static safe
template that preserves the original urgency and adds a disclaimer.

Public API
----------
    from agent.guardrails import apply_guardrails

    result = apply_guardrails(result, triage_urgency="MEDIUM")
    # returns result unchanged if clean, or safe fallback if violated
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Forbidden phrases  (case-insensitive substring match)
# ---------------------------------------------------------------------------

FORBIDDEN_PHRASES: list[str] = [
    "you don't have cancer",
    "you do not have cancer",
    "no cancer",
    "not cancer",
    "cancer free",
    "cancer-free",
    "you are fine",
    "you're fine",
    "nothing to worry about",
    "no need to see a doctor",
    "no need to visit a doctor",
    "does not need medical attention",
    "doesn't need medical attention",
    "not serious",
    "completely benign",                # absolute claim — not appropriate for AI
    "definitely not melanoma",
    "100% benign",
    "guaranteed benign",
]

# Compiled pattern for fast matching
_FORBIDDEN_RE = re.compile(
    "|".join(re.escape(p) for p in FORBIDDEN_PHRASES),
    flags=re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Static safe fallback templates (keyed by urgency level)
# ---------------------------------------------------------------------------

_SAFE_TEMPLATES: dict[str, dict] = {
    "HIGH": {
        "guardrail_triggered": True,
        "guardrail_reason": "LLM output violated safety rules; replaced with safe template.",
        "referral_message": (
            "This case has been flagged as URGENT due to red-flag symptoms. "
            "Please arrange an immediate in-person dermatology evaluation. "
            "Monitor the lesion and consult a doctor if it changes."
        ),
        "advice": "Monitor and consult a doctor if it changes.",
        "disclaimer": (
            "This is AI-assisted screening only. A qualified dermatologist "
            "must confirm any diagnosis."
        ),
    },
    "MEDIUM": {
        "guardrail_triggered": True,
        "guardrail_reason": "LLM output violated safety rules; replaced with safe template.",
        "explanation": (
            "The AI system has identified features that warrant further clinical review. "
            "Please book a dermatology appointment for a thorough evaluation. "
            "Monitor and consult a doctor if it changes."
        ),
        "advice": "Monitor and consult a doctor if it changes.",
        "disclaimer": (
            "This is AI-assisted screening only. A qualified dermatologist "
            "must confirm any diagnosis."
        ),
    },
    "LOW": {
        "guardrail_triggered": True,
        "guardrail_reason": "LLM output violated safety rules; replaced with safe template.",
        "explanation": (
            "The AI system has reviewed the image. Regular skin self-examination "
            "is recommended. "
            "Monitor and consult a doctor if it changes."
        ),
        "advice": "Monitor and consult a doctor if it changes.",
        "disclaimer": (
            "This is AI-assisted screening only. A qualified dermatologist "
            "must confirm any diagnosis. This output does not rule out any condition."
        ),
    },
}


# ---------------------------------------------------------------------------
# Urgency mapping from agent status strings -> canonical urgency level
# ---------------------------------------------------------------------------

_STATUS_TO_URGENCY: dict[str, str] = {
    "URGENT":         "HIGH",
    "NEEDS_MORE_INFO": "MEDIUM",
    "NORMAL":         "LOW",
    # explicit level strings (in case result carries them directly)
    "HIGH":   "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW":    "LOW",
}


# ---------------------------------------------------------------------------
# Core check functions
# ---------------------------------------------------------------------------

def _has_forbidden_phrase(text: str) -> tuple[bool, str]:
    """Returns (found, matched_phrase)."""
    m = _FORBIDDEN_RE.search(text)
    if m:
        return True, m.group(0)
    return False, ""


def _urgency_changed(result: dict, triage_urgency: str) -> bool:
    """
    True if the result dict contains an urgency field that does NOT match
    the urgency set by triage/scoring.py.

    'status' field in result is treated as proxy for urgency when present.
    """
    result_status = result.get("status", "")
    mapped = _STATUS_TO_URGENCY.get(result_status.upper(), "")
    if mapped and mapped != triage_urgency.upper():
        return True

    # Also check if result has an explicit 'urgency' key (future-proofing)
    result_urgency = result.get("urgency", "")
    if result_urgency and result_urgency.upper() != triage_urgency.upper():
        return True

    return False


def _collect_all_text(result: dict) -> str:
    """Concatenate all string values in result for forbidden-phrase scanning."""
    parts = []
    for v in result.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(i) for i in v if isinstance(i, str))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_guardrails(
    result: dict,
    triage_urgency: str,
) -> dict:
    """
    Check the LLM result dict against safety rules.

    Parameters
    ----------
    result : dict
        The result dict assembled by an agent branch node.
    triage_urgency : str
        The urgency level from triage/scoring.py ("HIGH" | "MEDIUM" | "LOW").
        The LLM is NOT allowed to change this.

    Returns
    -------
    dict
        Unchanged result if all checks pass.
        Safe fallback template (with guardrail_triggered=True) if any check fails.
        The fallback always carries the original status, predicted_class, confidence.
    """
    violations: list[str] = []

    # Rule 1: urgency unchanged
    if _urgency_changed(result, triage_urgency):
        violations.append(
            f"Urgency mismatch: triage={triage_urgency}, "
            f"LLM result status={result.get('status', 'N/A')}"
        )

    # Rule 2: no forbidden phrases
    all_text = _collect_all_text(result)
    found, phrase = _has_forbidden_phrase(all_text)
    if found:
        violations.append(f"Forbidden phrase detected: {phrase!r}")

    if not violations:
        return result

    # -- Build safe fallback --------------------------------------------------
    urgency_key = triage_urgency.upper() if triage_urgency.upper() in _SAFE_TEMPLATES else "MEDIUM"
    fallback = dict(_SAFE_TEMPLATES[urgency_key])   # shallow copy

    # Preserve non-sensitive fields from the original result
    for key in ("status", "predicted_class", "confidence", "triggered_red_flags",
                "top3_differential", "sources"):
        if key in result:
            fallback[key] = result[key]

    fallback["guardrail_violations"] = violations

    import logging
    logging.getLogger(__name__).warning(
        "Guardrail triggered: %s", "; ".join(violations)
    )

    return fallback
