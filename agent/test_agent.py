"""
agent/test_agent.py
-------------------
Three test cases that each trigger a DIFFERENT branch of the orchestrator.

Run with:
    python -m agent.test_agent          (from project root)
  or
    python agent/test_agent.py

Expected output
---------------
  [Test 1] Branch triggered: urgent    ← red flag (bleeding) overrides low confidence
  [Test 2] Branch triggered: followup  ← low confidence, no red flags
  [Test 3] Branch triggered: normal    ← high confidence, no red flags

The Gemini API is called for tests 1–3. Set GEMINI_API_KEY in your .env file
before running.
"""

from __future__ import annotations

import json
import sys
import os

# Allow running as a script from any working directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.graph import orchestrator  # noqa: E402  (after sys.path patch)

# ---------------------------------------------------------------------------
# Test inputs
# ---------------------------------------------------------------------------

TEST_CASES: list[dict] = [
    # ── Test 1: URGENT ───────────────────────────────────────────────────────
    # Confidence is LOW (0.42), but red-flag symptoms are present.
    # Expected branch: URGENT  (red flags win regardless of confidence)
    {
        "_label": "Test 1 — URGENT (low confidence + red flags)",
        "confidence": 0.42,
        "predicted_class": "MEL",
        "symptoms": {
            "bleeding": True,
            "rapid_growth": True,
            "irregular_border": False,
            "itching": False,
            "pain": False,
        },
    },
    # ── Test 2: FOLLOW-UP ────────────────────────────────────────────────────
    # Confidence is LOW (0.38), and NO red-flag symptoms.
    # Expected branch: FOLLOWUP
    {
        "_label": "Test 2 — FOLLOW-UP (low confidence, no red flags)",
        "confidence": 0.38,
        "predicted_class": "BKL",
        "symptoms": {
            "bleeding": False,
            "rapid_growth": False,
            "irregular_border": False,
            "itching": False,
            "pain": False,
        },
    },
    # ── Test 3: NORMAL ───────────────────────────────────────────────────────
    # Confidence is HIGH (0.91), and NO red-flag symptoms.
    # Expected branch: NORMAL
    {
        "_label": "Test 3 — NORMAL (high confidence, no red flags)",
        "confidence": 0.91,
        "predicted_class": "NV",
        "symptoms": {
            "bleeding": False,
            "rapid_growth": False,
            "irregular_border": False,
            "itching": True,   # itching alone, without pain → NOT urgent
            "pain": False,
        },
    },
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

SEPARATOR = "─" * 70


def run_tests() -> None:
    print(f"\n{'═' * 70}")
    print("  Dermatology Orchestrator — Branch Verification Test")
    print(f"{'═' * 70}\n")

    passed = 0
    expected_branches = [
        "urgent",   # Test 1
        "followup", # Test 2
        "normal",   # Test 3
    ]

    for i, (test_input, expected) in enumerate(
        zip(TEST_CASES, expected_branches), start=1
    ):
        label = test_input.pop("_label")
        print(f"{SEPARATOR}")
        print(f"  {label}")
        print(SEPARATOR)

        try:
            final_state = orchestrator.invoke(test_input)
            branch = final_state.get("branch", "UNKNOWN")
            result = final_state.get("result", {})

            status_symbol = "✓" if branch == expected else "✗"
            print(f"\n  [{status_symbol}] Branch triggered : {branch.upper()}")
            print(f"      Expected       : {expected.upper()}")
            print(f"      Result status  : {result.get('status', 'N/A')}")

            # Pretty-print result (truncate long LLM text for readability)
            for key, val in result.items():
                if key == "status":
                    continue
                if isinstance(val, str) and len(val) > 120:
                    val = val[:117] + "..."
                print(f"      {key:<25}: {val}")

            if branch == expected:
                passed += 1
            else:
                print(f"\n  ⚠ UNEXPECTED BRANCH — check triage_node logic")

        except Exception as exc:  # noqa: BLE001
            print(f"\n  [✗] ERROR in test {i}: {exc}")
            import traceback
            traceback.print_exc()

        print()

    print(f"{'═' * 70}")
    print(f"  Results: {passed}/{len(TEST_CASES)} tests hit the expected branch")
    print(f"{'═' * 70}\n")

    if passed < len(TEST_CASES):
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
