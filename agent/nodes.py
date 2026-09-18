"""
agent/nodes.py
--------------
The four node functions that make up the LangGraph graph:

  1. triage_node       — pure Python; sets state["branch"] (no LLM call)
  2. urgent_flag_node  — Gemini API; generates priority referral message
  3. ask_followup_node — Gemini API; generates clarifying symptom questions
  4. normal_result_node — Gemini API; generates structured explanation

Branch priority enforced in triage_node:
  1st  Red flag present (any confidence) → URGENT
  2nd  No red flag + confidence < threshold → FOLLOWUP
  3rd  No red flag + confidence ≥ threshold → NORMAL
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from .config import (
    BRANCH_FOLLOWUP,
    BRANCH_NORMAL,
    BRANCH_URGENT,
    CONFIDENCE_THRESHOLD,
    RED_FLAG_SYMPTOMS,
    URGENT_COMBO,
)
from .state import AgentState

load_dotenv()

# ---------------------------------------------------------------------------
# Shared LLM — initialised once, reused across all Gemini node calls
# ---------------------------------------------------------------------------

def _get_llm() -> ChatGoogleGenerativeAI:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=0.3,
    )


# ---------------------------------------------------------------------------
# Helper: detect red flags in symptom dict
# ---------------------------------------------------------------------------

def _has_red_flag(symptoms: dict[str, bool]) -> tuple[bool, list[str]]:
    """
    Returns (flag_found, list_of_triggered_flags).

    Checks individual red-flag symptoms first, then the itching+pain combo.
    """
    triggered: list[str] = []

    for symptom in RED_FLAG_SYMPTOMS:
        if symptoms.get(symptom, False):
            triggered.append(symptom)

    combo_a, combo_b = URGENT_COMBO
    if symptoms.get(combo_a, False) and symptoms.get(combo_b, False):
        triggered.append(f"{combo_a}+{combo_b}")

    return bool(triggered), triggered


# ---------------------------------------------------------------------------
# Node 1: triage_node  (pure Python — no LLM)
# ---------------------------------------------------------------------------

def triage_node(state: AgentState) -> AgentState:
    """
    Reads confidence + symptoms; sets state["branch"].

    Priority order:
      1. Any red flag → URGENT  (confidence is irrelevant)
      2. No red flag + confidence < threshold → FOLLOWUP
      3. No red flag + confidence ≥ threshold → NORMAL
    """
    symptoms: dict[str, bool] = state.get("symptoms", {})
    confidence: float = state.get("confidence", 0.0)

    flag_found, triggered_flags = _has_red_flag(symptoms)

    if flag_found:
        branch = BRANCH_URGENT
    elif confidence < CONFIDENCE_THRESHOLD:
        branch = BRANCH_FOLLOWUP
    else:
        branch = BRANCH_NORMAL

    print(
        f"[triage_node] confidence={confidence:.2f} | "
        f"red_flags={triggered_flags or 'none'} | branch → {branch}"
    )
    return {"branch": branch}


# ---------------------------------------------------------------------------
# Node 2: urgent_flag_node  (Gemini)
# ---------------------------------------------------------------------------

def urgent_flag_node(state: AgentState) -> AgentState:
    """
    Generates a priority referral message for cases with red-flag symptoms.
    """
    predicted_class: str = state.get("predicted_class", "Unknown")
    confidence: float = state.get("confidence", 0.0)
    symptoms: dict[str, bool] = state.get("symptoms", {})
    _, triggered_flags = _has_red_flag(symptoms)

    prompt = f"""You are an AI assistant supporting a dermatology diagnostic system.

A patient's skin lesion image has been analysed with the following results:
- Predicted class: {predicted_class}
- Model confidence: {confidence:.0%}
- Concerning symptoms reported: {', '.join(triggered_flags)}

One or more RED-FLAG symptoms have been detected. Generate a clear, concise 
priority referral message for the clinician dashboard. The message must:
1. State that this case is marked URGENT.
2. List the specific red-flag symptoms found.
3. Recommend immediate in-person evaluation by a dermatologist.
4. Be professional and avoid causing unnecessary patient panic.
5. Be no longer than 4 sentences.

Do NOT provide a diagnosis. Only recommend urgent referral."""

    llm = _get_llm()
    response = llm.invoke(prompt)
    referral_message: str = response.content

    result: dict[str, Any] = {
        "status": "URGENT",
        "predicted_class": predicted_class,
        "confidence": confidence,
        "triggered_red_flags": triggered_flags,
        "referral_message": referral_message,
    }
    print(f"[urgent_flag_node] URGENT result generated. flags={triggered_flags}")
    return {"result": result}


# ---------------------------------------------------------------------------
# Node 3: ask_followup_node  (Gemini)
# ---------------------------------------------------------------------------

def ask_followup_node(state: AgentState) -> AgentState:
    """
    Generates targeted follow-up questions when model confidence is low
    and no red flags are present.
    """
    predicted_class: str = state.get("predicted_class", "Unknown")
    confidence: float = state.get("confidence", 0.0)
    symptoms: dict[str, bool] = state.get("symptoms", {})

    answered = [k for k, v in symptoms.items() if v]
    unanswered_hint = "The patient has not reported any notable symptoms so far."
    if answered:
        unanswered_hint = f"Symptoms already reported as present: {', '.join(answered)}."

    prompt = f"""You are an AI assistant supporting a dermatology diagnostic system.

A skin lesion image was analysed but the model's confidence is low ({confidence:.0%}),
with a tentative prediction of "{predicted_class}".
{unanswered_hint}

Because the image alone is inconclusive, generate a SHORT list of 3–5 targeted 
follow-up questions to ask the patient. The questions should:
1. Help distinguish between similar skin conditions.
2. Ask about symptom duration, changes over time, family history if relevant.
3. Be phrased in plain, patient-friendly language (no jargon).
4. Not repeat symptoms already confirmed as present.

Return ONLY the numbered list of questions, no preamble."""

    llm = _get_llm()
    response = llm.invoke(prompt)
    questions: str = response.content

    result: dict[str, Any] = {
        "status": "NEEDS_MORE_INFO",
        "predicted_class": predicted_class,
        "confidence": confidence,
        "followup_questions": questions,
    }
    print(f"[ask_followup_node] Follow-up questions generated. confidence={confidence:.2f}")
    return {"result": result}


# ---------------------------------------------------------------------------
# Node 4: normal_result_node  (Gemini)
# ---------------------------------------------------------------------------

def normal_result_node(state: AgentState) -> AgentState:
    """
    Generates a structured, patient-friendly explanation for a confident,
    non-urgent prediction.
    """
    predicted_class: str = state.get("predicted_class", "Unknown")
    confidence: float = state.get("confidence", 0.0)
    symptoms: dict[str, bool] = state.get("symptoms", {})

    reported_symptoms = [k for k, v in symptoms.items() if v] or ["none reported"]

    prompt = f"""You are an AI assistant supporting a dermatology diagnostic system.

A patient's skin lesion image has been classified with high confidence:
- Predicted class: {predicted_class}
- Model confidence: {confidence:.0%}
- Symptoms reported: {', '.join(reported_symptoms)}

Generate a structured, patient-friendly diagnostic explanation. Include:
1. A brief plain-English description of what "{predicted_class}" typically is.
2. How common it is and who is typically affected.
3. General advice (e.g. monitor for changes, apply sunscreen, see a doctor 
   for confirmation — choose what is appropriate for this condition).
4. A clear disclaimer: this is AI-assisted screening only; a qualified 
   dermatologist must confirm the diagnosis.

Keep the response under 150 words. Use a calm, reassuring tone."""

    llm = _get_llm()
    response = llm.invoke(prompt)
    explanation: str = response.content

    result: dict[str, Any] = {
        "status": "NORMAL",
        "predicted_class": predicted_class,
        "confidence": confidence,
        "explanation": explanation,
    }
    print(f"[normal_result_node] Normal result generated. class={predicted_class}, confidence={confidence:.2f}")
    return {"result": result}
