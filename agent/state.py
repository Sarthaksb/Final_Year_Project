"""
agent/state.py
--------------
Defines AgentState — the single shared TypedDict that flows through every
node in the LangGraph graph.

All node functions receive and return (a subset of) this dict.
LangGraph merges the returned dict into the current state automatically.
"""

from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """
    Fields
    ------
    confidence : float
        Softmax probability of the predicted class (0.0 – 1.0).
    predicted_class : str
        Model's top-1 prediction, e.g. "MEL", "NV", "BCC" …
    symptoms : dict[str, bool]
        Answers to the symptom questionnaire.
        Expected keys (all optional, default False if absent):
            rapid_growth, bleeding, irregular_border, itching, pain,
            color_change, size_change, ulceration
    branch : str
        Set by triage_node; one of "urgent" | "followup" | "normal".
    result : dict[str, Any]
        Final output payload assembled by the branch node.
    """

    confidence: float
    predicted_class: str
    symptoms: dict[str, bool]
    branch: str
    result: dict[str, Any]
