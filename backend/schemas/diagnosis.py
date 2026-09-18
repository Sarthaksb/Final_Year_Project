"""
backend/schemas/diagnosis.py
------------------------------
Re-exports DiagnosisOut and SymptomForm from schemas/case.py.
Exists as a convenience alias — other modules may import from here
instead of schemas.case to match the conceptual grouping.
"""

from schemas.case import DiagnosisOut, SymptomForm  # noqa: F401
