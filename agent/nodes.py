"""
agent/nodes.py
--------------
The four node functions that make up the LangGraph graph:

  1. triage_node        -- pure Python; sets state["branch"] + top3_differential
  2. urgent_flag_node   -- Gemini API; referral message + RAG sources + guardrail
  3. ask_followup_node  -- Gemini API; follow-up questions + RAG sources + guardrail
  4. normal_result_node -- Gemini API; explanation + RAG sources + guardrail

Branch priority enforced in triage_node:
  1st  Red flag present (any confidence) -> URGENT
  2nd  No red flag + confidence < threshold -> FOLLOWUP
  3rd  No red flag + confidence >= threshold -> NORMAL

Phase 11B additions:
  - RAG: guideline chunks retrieved for predicted class + symptoms, injected in prompt
  - Guardrails: post-generation check (urgency unchanged, no forbidden phrases)
  - Top-3 differential: computed in triage_node from all_probabilities
  - Result always includes "sources" (RAG doc names) and "top3_differential"
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
from .guardrails import apply_guardrails

load_dotenv()

# Class descriptions (mirror predict.py -- kept local to avoid ML import overhead)
_CLASS_DESCRIPTIONS = {
    "MEL":  "Melanoma",
    "NV":   "Melanocytic Nevus",
    "BCC":  "Basal Cell Carcinoma",
    "AK":   "Actinic Keratosis",
    "BKL":  "Benign Keratosis-like Lesion",
    "DF":   "Dermatofibroma",
    "VASC": "Vascular Lesion",
    "SCC":  "Squamous Cell Carcinoma",
}

# ---------------------------------------------------------------------------
# Shared LLM -- initialised once, reused across all Gemini node calls
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
# RAG helper -- graceful: returns empty list if index not ready
# ---------------------------------------------------------------------------

def _retrieve_guidelines(predicted_class: str, symptoms: dict[str, bool], k: int = 3) -> list[dict]:
    """
    Query RAG for guideline chunks relevant to this case.
    Query = predicted class + active symptoms.
    Returns [] if RAG index not available (never crashes the pipeline).
    """
    try:
        from .rag import retrieve
        active = [s for s, v in symptoms.items() if v]
        query = f"{predicted_class} skin lesion " + (" ".join(active) if active else "management guidelines")
        return retrieve(query, k=k)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("RAG unavailable: %s", exc)
        return []


def _format_rag_context(chunks: list[dict]) -> tuple[str, list[str]]:
    """
    Returns (context_block, source_names_list).
    context_block is the text to inject into the prompt.
    """
    if not chunks:
        return "", []
    lines = ["--- Dermatology Guidelines (for context only) ---"]
    sources = []
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"[{i}] {chunk['text']}")
        src = chunk.get("source", "unknown")
        if src not in sources:
            sources.append(src)
    lines.append("--- End of guidelines ---")
    return "\n".join(lines), sources


# ---------------------------------------------------------------------------
# Top-3 differential helper
# ---------------------------------------------------------------------------

def _compute_top3(all_probabilities: dict[str, float]) -> list[dict]:
    """Return top-3 classes by probability, descending."""
    if not all_probabilities:
        return []
    sorted_probs = sorted(all_probabilities.items(), key=lambda x: x[1], reverse=True)
    return [
        {
            "class":       cls,
            "probability": round(prob, 4),
            "description": _CLASS_DESCRIPTIONS.get(cls, cls),
        }
        for cls, prob in sorted_probs[:3]
    ]


# ---------------------------------------------------------------------------
# Helper: detect red flags in symptom dict
# ---------------------------------------------------------------------------

def _has_red_flag(symptoms: dict[str, bool]) -> tuple[bool, list[str]]:
    """Returns (flag_found, list_of_triggered_flags)."""
    triggered: list[str] = []
    for symptom in RED_FLAG_SYMPTOMS:
        if symptoms.get(symptom, False):
            triggered.append(symptom)
    combo_a, combo_b = URGENT_COMBO
    if symptoms.get(combo_a, False) and symptoms.get(combo_b, False):
        triggered.append(f"{combo_a}+{combo_b}")
    return bool(triggered), triggered


# ---------------------------------------------------------------------------
# Node 1: triage_node  (pure Python -- no LLM)
# ---------------------------------------------------------------------------

def triage_node(state: AgentState) -> AgentState:
    """
    Reads confidence + symptoms; sets state["branch"] and state["top3_differential"].

    Priority order:
      1. Any red flag -> URGENT  (confidence is irrelevant)
      2. No red flag + confidence < threshold -> FOLLOWUP
      3. No red flag + confidence >= threshold -> NORMAL
    """
    symptoms: dict[str, bool] = state.get("symptoms", {})
    confidence: float = state.get("confidence", 0.0)
    all_probs: dict[str, float] = state.get("all_probabilities", {})

    flag_found, triggered_flags = _has_red_flag(symptoms)

    if flag_found:
        branch = BRANCH_URGENT
    elif confidence < CONFIDENCE_THRESHOLD:
        branch = BRANCH_FOLLOWUP
    else:
        branch = BRANCH_NORMAL

    top3 = _compute_top3(all_probs)

    print(
        f"[triage_node] confidence={confidence:.2f} | "
        f"red_flags={triggered_flags or 'none'} | branch -> {branch} | "
        f"top3={[d['class'] for d in top3]}"
    )
    return {"branch": branch, "top3_differential": top3}


# ---------------------------------------------------------------------------
# Node 2: urgent_flag_node  (Gemini)
# ---------------------------------------------------------------------------

def urgent_flag_node(state: AgentState) -> AgentState:
    """
    Generates a priority referral message for cases with red-flag symptoms.
    Injects RAG guidelines into prompt. Applies guardrail post-generation.
    """
    predicted_class: str = state.get("predicted_class", "Unknown")
    confidence: float = state.get("confidence", 0.0)
    symptoms: dict[str, bool] = state.get("symptoms", {})
    top3: list[dict] = state.get("top3_differential", [])
    _, triggered_flags = _has_red_flag(symptoms)

    # RAG retrieval
    chunks = _retrieve_guidelines(predicted_class, symptoms, k=3)
    rag_context, sources = _format_rag_context(chunks)

    top3_text = "\n".join(
        f"  {i+1}. {d['class']} ({d['description']}): {d['probability']:.0%}"
        for i, d in enumerate(top3)
    ) if top3 else "  (not available)"

    prompt = f"""You are an AI assistant supporting a dermatology diagnostic system.
This is DECISION SUPPORT only -- you must NEVER diagnose or say the patient is fine.

A patient's skin lesion image has been analysed with the following results:
- Predicted class: {predicted_class} ({_CLASS_DESCRIPTIONS.get(predicted_class, '')})
- Model confidence: {confidence:.0%}
- Concerning symptoms reported: {', '.join(triggered_flags)}

Top-3 differential (by probability):
{top3_text}

{rag_context}

One or more RED-FLAG symptoms have been detected. Generate a clear, concise
priority referral message for the clinician dashboard. The message must:
1. State that this case is marked URGENT.
2. List the specific red-flag symptoms found.
3. Reference relevant guideline points from the context above if applicable.
4. Recommend immediate in-person evaluation by a dermatologist.
5. Be professional and avoid causing unnecessary patient panic.
6. Include: "Monitor and consult a doctor if it changes."
7. Be no longer than 5 sentences.

FORBIDDEN: Do NOT say "no cancer", "you are fine", "nothing to worry about",
or any phrase that dismisses the need for medical review.
Do NOT provide a diagnosis. Only recommend urgent referral."""

    llm = _get_llm()
    response = llm.invoke(prompt)
    referral_message: str = response.content

    result: dict[str, Any] = {
        "status":              "URGENT",
        "predicted_class":     predicted_class,
        "confidence":          confidence,
        "triggered_red_flags": triggered_flags,
        "referral_message":    referral_message,
        "top3_differential":   top3,
        "sources":             sources,
        "advice":              "Monitor and consult a doctor if it changes.",
        "disclaimer":          "This is AI-assisted screening only. A dermatologist must confirm any diagnosis.",
    }

    # Apply guardrails (urgency=HIGH because red flags are present)
    result = apply_guardrails(result, triage_urgency="HIGH")

    print(f"[urgent_flag_node] URGENT result generated. flags={triggered_flags} | sources={sources}")
    return {"result": result}


# ---------------------------------------------------------------------------
# Node 3: ask_followup_node  (Gemini)
# ---------------------------------------------------------------------------

def ask_followup_node(state: AgentState) -> AgentState:
    """
    Generates targeted follow-up questions when model confidence is low
    and no red flags are present. Injects RAG + guardrail.
    """
    predicted_class: str = state.get("predicted_class", "Unknown")
    confidence: float = state.get("confidence", 0.0)
    symptoms: dict[str, bool] = state.get("symptoms", {})
    top3: list[dict] = state.get("top3_differential", [])

    answered = [k for k, v in symptoms.items() if v]
    unanswered_hint = "The patient has not reported any notable symptoms so far."
    if answered:
        unanswered_hint = f"Symptoms already reported as present: {', '.join(answered)}."

    # RAG retrieval
    chunks = _retrieve_guidelines(predicted_class, symptoms, k=3)
    rag_context, sources = _format_rag_context(chunks)

    top3_text = "\n".join(
        f"  {i+1}. {d['class']} ({d['description']}): {d['probability']:.0%}"
        for i, d in enumerate(top3)
    ) if top3 else "  (not available)"

    prompt = f"""You are an AI assistant supporting a dermatology diagnostic system.
This is DECISION SUPPORT only -- you must NEVER diagnose or say the patient is fine.

A skin lesion image was analysed but the model's confidence is low ({confidence:.0%}),
with a tentative prediction of "{predicted_class}" ({_CLASS_DESCRIPTIONS.get(predicted_class, '')}).
{unanswered_hint}

Top-3 differential (by probability):
{top3_text}

{rag_context}

Because the image alone is inconclusive, generate a SHORT list of 3-5 targeted
follow-up questions to ask the patient. The questions should:
1. Help distinguish between the top differential diagnoses listed above.
2. Be informed by the guideline context above (e.g. ask about duration, changes, family history).
3. Be phrased in plain, patient-friendly language (no jargon).
4. Not repeat symptoms already confirmed as present.

After the questions, add one sentence: "Monitor and consult a doctor if it changes."

FORBIDDEN: Do NOT say "no cancer", "you are fine", "nothing to worry about",
or any phrase that dismisses the need for medical review.

Return ONLY the numbered list of questions + the closing sentence, no preamble."""

    llm = _get_llm()
    response = llm.invoke(prompt)
    questions: str = response.content

    result: dict[str, Any] = {
        "status":            "NEEDS_MORE_INFO",
        "predicted_class":   predicted_class,
        "confidence":        confidence,
        "followup_questions": questions,
        "top3_differential": top3,
        "sources":           sources,
        "advice":            "Monitor and consult a doctor if it changes.",
        "disclaimer":        "This is AI-assisted screening only. A dermatologist must confirm any diagnosis.",
    }

    # Guardrail: MEDIUM urgency (low confidence, no red flags)
    result = apply_guardrails(result, triage_urgency="MEDIUM")

    print(f"[ask_followup_node] Follow-up questions generated. confidence={confidence:.2f} | sources={sources}")
    return {"result": result}


# ---------------------------------------------------------------------------
# Node 4: normal_result_node  (Gemini)
# ---------------------------------------------------------------------------

def normal_result_node(state: AgentState) -> AgentState:
    """
    Generates a structured, patient-friendly explanation for a confident,
    non-urgent prediction. Injects RAG + guardrail.
    """
    predicted_class: str = state.get("predicted_class", "Unknown")
    confidence: float = state.get("confidence", 0.0)
    symptoms: dict[str, bool] = state.get("symptoms", {})
    top3: list[dict] = state.get("top3_differential", [])

    reported_symptoms = [k for k, v in symptoms.items() if v] or ["none reported"]

    # RAG retrieval
    chunks = _retrieve_guidelines(predicted_class, symptoms, k=3)
    rag_context, sources = _format_rag_context(chunks)

    top3_text = "\n".join(
        f"  {i+1}. {d['class']} ({d['description']}): {d['probability']:.0%}"
        for i, d in enumerate(top3)
    ) if top3 else "  (not available)"

    prompt = f"""You are an AI assistant supporting a dermatology diagnostic system.
This is DECISION SUPPORT only -- you must NEVER diagnose or say the patient is fine.

A patient's skin lesion image has been classified with high confidence:
- Predicted class: {predicted_class} ({_CLASS_DESCRIPTIONS.get(predicted_class, '')})
- Model confidence: {confidence:.0%}
- Symptoms reported: {', '.join(reported_symptoms)}

Top-3 differential (by probability):
{top3_text}

{rag_context}

Generate a structured, patient-friendly diagnostic explanation. Include:
1. A brief plain-English description of what "{predicted_class}" typically is,
   drawing on the guideline context above.
2. How common it is and who is typically affected.
3. General advice appropriate for this condition (e.g. monitoring, sun protection,
   follow-up timeline) -- reference the guideline context where relevant.
4. End with: "Monitor and consult a doctor if it changes."
5. A clear disclaimer: "This is AI-assisted screening only; a qualified
   dermatologist must confirm the diagnosis."

Keep the response under 180 words. Use a calm, informative tone.

FORBIDDEN: Do NOT say "no cancer", "you are fine", "nothing to worry about",
"completely benign", "guaranteed benign", or any phrase that dismisses the need
for medical review. This is decision support, not diagnosis."""

    llm = _get_llm()
    response = llm.invoke(prompt)
    explanation: str = response.content

    result: dict[str, Any] = {
        "status":            "NORMAL",
        "predicted_class":   predicted_class,
        "confidence":        confidence,
        "explanation":       explanation,
        "top3_differential": top3,
        "sources":           sources,
        "advice":            "Monitor and consult a doctor if it changes.",
        "disclaimer":        "This is AI-assisted screening only. A dermatologist must confirm any diagnosis.",
    }

    # Guardrail: LOW urgency (high confidence, no red flags)
    result = apply_guardrails(result, triage_urgency="LOW")

    print(f"[normal_result_node] Normal result generated. class={predicted_class} | sources={sources}")
    return {"result": result}
