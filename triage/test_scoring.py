"""
triage/test_scoring.py
----------------------
Quick test covering every urgency branch of compute_urgency().

Run with:
    python -m triage.test_scoring          (from project root)
  or
    python triage/test_scoring.py

Expected output
---------------
  Test 1  HIGH   -- red-flag symptom (bleeding), confidence irrelevant
  Test 2  HIGH   -- itching+pain combo, confidence irrelevant
  Test 3  MEDIUM -- no red flag, low confidence (0.45)
  Test 4  MEDIUM -- no red flag, high confidence but high-risk class MEL
  Test 5  LOW    -- no red flag, high confidence, benign class NV
              (disclaimer must be present in reasons)
  Test 6  MEDIUM -- NV high-confidence but malignancy score 0.35 (>= 0.30)
  Test 7  MEDIUM -- NV high-confidence but P(MEL)=0.22 (>= 0.20 threshold)
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from triage.scoring import TriageResult, compute_urgency

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

CASES: list[dict] = [
    # ── HIGH: individual red-flag symptom, low confidence ──────────────────
    {
        "_label":          "Test 1 — HIGH (red flag: bleeding, low confidence)",
        "_expected":       "HIGH",
        "confidence":      0.42,
        "predicted_class": "BKL",
        "symptoms": {
            "bleeding":          True,
            "rapid_growth":      False,
            "irregular_border":  False,
            "itching":           False,
            "pain":              False,
        },
    },
    # ── HIGH: itching+pain combo, high confidence ───────────────────────────
    {
        "_label":          "Test 2 — HIGH (itching+pain combo, high confidence)",
        "_expected":       "HIGH",
        "confidence":      0.88,
        "predicted_class": "NV",
        "symptoms": {
            "bleeding":          False,
            "rapid_growth":      False,
            "irregular_border":  False,
            "itching":           True,
            "pain":              True,
        },
    },
    # ── MEDIUM: no red flag, low confidence ─────────────────────────────────
    {
        "_label":          "Test 3 — MEDIUM (no red flag, low confidence 0.45)",
        "_expected":       "MEDIUM",
        "confidence":      0.45,
        "predicted_class": "BCC",
        "symptoms": {
            "bleeding":          False,
            "rapid_growth":      False,
            "irregular_border":  False,
            "itching":           False,
            "pain":              False,
        },
    },
    # ── MEDIUM: no red flag, high confidence but malignant class MEL ────────
    {
        "_label":          "Test 4 — MEDIUM (no red flag, high confidence, high-risk class MEL)",
        "_expected":       "MEDIUM",
        "confidence":      0.81,
        "predicted_class": "MEL",
        "symptoms": {
            "bleeding":          False,
            "rapid_growth":      False,
            "irregular_border":  False,
            "itching":           True,   # itching alone (no pain) → NOT urgent
            "pain":              False,
        },
    },
    # -- LOW: no red flag, high confidence, low-risk class -- disclaimer required
    {
        "_label":          "Test 5 -- LOW  (no red flag, high confidence, benign class NV)",
        "_expected":       "LOW",
        "_check_disclaimer": True,
        "confidence":      0.93,
        "predicted_class": "NV",
        "symptoms": {
            "bleeding":          False,
            "rapid_growth":      False,
            "irregular_border":  False,
            "itching":           False,
            "pain":              False,
        },
    },
    # -- MEDIUM: high-confidence NV but malignancy score 0.35 (>= 0.30) --------
    {
        "_label":          "Test 6 -- MEDIUM (NV high-conf, malignancy score=0.35 >= 0.30)",
        "_expected":       "MEDIUM",
        "_check_disclaimer": False,
        "confidence":      0.88,
        "predicted_class": "NV",
        "symptoms": {
            "bleeding":          False,
            "rapid_growth":      False,
            "irregular_border":  False,
            "itching":           False,
            "pain":              False,
        },
        "all_probabilities": {
            "MEL": 0.10, "NV": 0.55, "BCC": 0.20, "AK": 0.05,
            "BKL": 0.05, "DF": 0.01, "VASC": 0.01, "SCC": 0.03,
        },
    },
    # -- MEDIUM: high-confidence NV but P(MEL)=0.22 >= 0.20 threshold ---------
    {
        "_label":          "Test 7 -- MEDIUM (NV high-conf, P(MEL)=0.22 >= 0.20)",
        "_expected":       "MEDIUM",
        "_check_disclaimer": False,
        "confidence":      0.75,
        "predicted_class": "NV",
        "symptoms": {
            "bleeding":          False,
            "rapid_growth":      False,
            "irregular_border":  False,
            "itching":           False,
            "pain":              False,
        },
        "all_probabilities": {
            "MEL": 0.22, "NV": 0.50, "BCC": 0.10, "AK": 0.05,
            "BKL": 0.05, "DF": 0.03, "VASC": 0.02, "SCC": 0.03,
        },
    },
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

SEP = "-" * 68

def run_tests() -> None:
    print("\n" + "=" * 68)
    print("  Triage Scoring -- Branch Verification Test")
    print("=" * 68 + "\n")

    passed = 0

    for case in CASES:
        label            = case.pop("_label")
        expected         = case.pop("_expected")
        check_disclaimer = case.pop("_check_disclaimer", False)

        result: TriageResult = compute_urgency(**case)

        ok = result.urgency == expected
        # Extra check: LOW must always include the disclaimer
        if ok and check_disclaimer:
            from agent.config import LOW_URGENCY_DISCLAIMER
            ok = any(LOW_URGENCY_DISCLAIMER in r for r in result.reasons)
            if not ok:
                print(f"  [FAIL] Disclaimer missing from LOW reasons!")
        symbol = "[PASS]" if ok else "[FAIL]"
        if ok:
            passed += 1

        print(SEP)
        print(f"  {label}")
        print(SEP)
        print(f"  {symbol} Urgency  : {result.urgency:<8}  (expected: {expected})")
        print(f"      Score    : {result.score}")
        print(f"      Reasons  :")
        for r in result.reasons:
            print(f"        * {r}")
        print()

    print("=" * 68)
    print(f"  Results: {passed}/{len(CASES)} tests matched expected urgency")
    print("=" * 68 + "\n")

    if passed < len(CASES):
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
