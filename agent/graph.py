"""
agent/graph.py
--------------
Builds and compiles the LangGraph StateGraph for the dermatology
orchestrator agent.

Graph topology
--------------

    [START]
       │
  triage_node          ← pure Python; sets state["branch"]
       │
  ┌────┼────────────┐
  │    │            │
urgent  followup   normal
  │    │            │
  └────┴────────────┘
            │
          [END]

The conditional edge reads state["branch"] and routes to the correct node.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .config import BRANCH_FOLLOWUP, BRANCH_NORMAL, BRANCH_URGENT
from .nodes import (
    ask_followup_node,
    normal_result_node,
    triage_node,
    urgent_flag_node,
)
from .state import AgentState


# ---------------------------------------------------------------------------
# Router function — used by the conditional edge
# ---------------------------------------------------------------------------

def _route_after_triage(state: AgentState) -> str:
    """Returns the name of the next node based on state["branch"]."""
    branch = state.get("branch", BRANCH_NORMAL)
    routing = {
        BRANCH_URGENT: "urgent_flag_node",
        BRANCH_FOLLOWUP: "ask_followup_node",
        BRANCH_NORMAL: "normal_result_node",
    }
    return routing.get(branch, "normal_result_node")


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """
    Constructs and compiles the orchestrator StateGraph.

    Returns the compiled graph, which exposes a `.invoke(state)` method.
    """
    graph = StateGraph(AgentState)

    # ── Add nodes ──────────────────────────────────────────────────────────
    graph.add_node("triage_node", triage_node)
    graph.add_node("urgent_flag_node", urgent_flag_node)
    graph.add_node("ask_followup_node", ask_followup_node)
    graph.add_node("normal_result_node", normal_result_node)

    # ── Entry point ────────────────────────────────────────────────────────
    graph.add_edge(START, "triage_node")

    # ── Conditional edge: triage → one of three branch nodes ───────────────
    graph.add_conditional_edges(
        "triage_node",
        _route_after_triage,
        {
            "urgent_flag_node": "urgent_flag_node",
            "ask_followup_node": "ask_followup_node",
            "normal_result_node": "normal_result_node",
        },
    )

    # ── All branch nodes terminate at END ──────────────────────────────────
    graph.add_edge("urgent_flag_node", END)
    graph.add_edge("ask_followup_node", END)
    graph.add_edge("normal_result_node", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Module-level compiled graph (import and call directly)
# ---------------------------------------------------------------------------

orchestrator = build_graph()
