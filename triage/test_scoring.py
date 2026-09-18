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
  Test 1  HIGH   — red-flag symptom (bleeding), confidence irrelevant
  Test 2  HIGH   — itching+pain combo, confidence irrelevant
  Test 3  MEDIUM — no red flag, low confidence (0.45)
  Test 4  MEDIUM — no red flag, high confidence but high-risk class MEL
  Test 5  LOW    — no red flag, high confidence, benign class NV
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
    # ── LOW: no red flag, high confidence, low-risk class ───────────────────
    {
        "_label":          "Test 5 — LOW  (no red flag, high confidence, benign class NV)",
        "_expected":       "LOW",
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
        label    = case.pop("_label")
        expected = case.pop("_expected")

        result: TriageResult = compute_urgency(**case)

        ok = result.urgency == expected
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
