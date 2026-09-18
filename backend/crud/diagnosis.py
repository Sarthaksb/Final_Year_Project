"""
backend/crud/diagnosis.py
--------------------------
Thin helpers for RAG pipeline integration within the diagnosis route.
Kept separate so the route file stays clean and testable.
"""

from pathlib import Path
import sys
from typing import Optional

# ── resolve project root so rag/ module is importable ──────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def run_rag(predicted_class: str) -> tuple[Optional[str], Optional[str]]:
    """
    Query the RAG pipeline for a text explanation grounded in the knowledge base.

    Returns
    -------
    (explanation, source) — both None if RAG is unavailable or knowledge base is empty.
    """
    try:
        from rag.retriever import retrieve_and_explain  # type: ignore
        result = retrieve_and_explain(predicted_class)
        return result.get("explanation"), result.get("source")
    except Exception as exc:
        print(f"[crud/diagnosis] RAG unavailable: {exc}")
        return None, None
