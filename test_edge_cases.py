import asyncio
import os

from triage.scoring import compute_urgency
from agent.graph import orchestrator

async def test_pipeline(scenario_name, predicted_class, confidence, symptoms,
                        all_probabilities=None):
    print(f"\n=======================================================")
    print(f"TEST: {scenario_name}")
    print(f"Input: {predicted_class} | Confidence: {confidence*100:.1f}%")
    print(f"Symptoms: {symptoms}")
    print(f"-------------------------------------------------------")

    # 1. Triage scoring
    try:
        triage_res = compute_urgency(confidence, predicted_class, symptoms,
                                     all_probabilities=all_probabilities)
        print(f"[TRIAGE] Level: {triage_res.urgency} (Score: {triage_res.score})")
        print(f"[TRIAGE] Reasons: {triage_res.reasons}")
    except Exception as e:
        print(f"[TRIAGE] Error: {e}")

    # 2. Agent Graph
    try:
        state = await orchestrator.ainvoke({
            "predicted_class": predicted_class,
            "confidence": confidence,
            "symptoms": symptoms
        })
        res = state.get("result", {})
        print(f"[AGENT] Branch chosen: {res.get('status')}")

        if 'explanation' in res:
            print(f"[AGENT] Explanation: {res.get('explanation')[:150]}...")
        if 'referral_message' in res:
            print(f"[AGENT] Referral: {res.get('referral_message')[:150]}...")
    except Exception as e:
        print(f"[AGENT] Error: {e}")

async def main():
    # Load environment for Gemini
    from dotenv import load_dotenv
    load_dotenv("backend/.env")

    if not os.getenv("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY not set. Agent calls may fail.")

    # Case 2: Blank/missing symptom answers
    await test_pipeline(
        "Blank/Missing Symptoms",
        "NV",
        0.85,
        {"rapid_growth": False, "bleeding": False, "irregular_border": False, "itching": False, "pain": False}
    )

    # Case 4: Contradictory symptoms (Frontend only sends bools, but let's test all TRUE)
    await test_pipeline(
        "Contradictory / All True Symptoms",
        "BKL",
        0.90,
        {"rapid_growth": True, "bleeding": True, "irregular_border": True, "itching": True, "pain": True}
    )

    # Case 5: Extremely low model confidence
    await test_pipeline(
        "Extremely Low Confidence (<30%)",
        "MEL",
        0.15,
        {"rapid_growth": False, "bleeding": False, "irregular_border": False, "itching": False, "pain": False}
    )

    # Case 6: Non-skin / OOD image (OOD gate fires in predict.py before triage runs)
    print(f"\n=======================================================")
    print(f"TEST: Non-skin / OOD image (gate simulation)")
    print(f"-------------------------------------------------------")
    print("[OOD] In production: predict() returns ood_rejected=True.")
    print("[OOD] Diagnosis route raises HTTP 422 status=invalid_image.")
    print("[OOD] No triage call, no Case document created. (No triage assert needed here.)")

    # Case 7: High-confidence NV with malignancy score 0.35 -> must be MEDIUM
    await test_pipeline(
        "High-conf NV but malignancy_score=0.35 (BCC=0.20+MEL=0.10+SCC=0.05) -> MEDIUM",
        "NV",
        0.88,
        {"rapid_growth": False, "bleeding": False, "irregular_border": False, "itching": False, "pain": False},
        all_probabilities={
            "MEL": 0.10, "NV": 0.55, "BCC": 0.20, "AK": 0.05,
            "BKL": 0.05, "DF": 0.01, "VASC": 0.01, "SCC": 0.03,
        },
    )

if __name__ == "__main__":
    asyncio.run(main())
