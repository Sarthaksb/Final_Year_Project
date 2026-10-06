"""
backend/api/routes/doctor.py
-----------------------------
Doctor-only endpoints (role = "doctor" required on every route).

Routes
------
GET  /api/doctor/stats                     — dashboard summary counts
GET  /api/doctor/cases                     — paginated list (all patients)
GET  /api/doctor/cases/{case_id}           — case detail (any patient)
POST /api/doctor/cases/{case_id}/review    — submit accept/override + notes
GET  /api/doctor/cases/{case_id}/report    — download PDF report

PDF generation uses reportlab (pure Python, no browser required).
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from api.dependencies import get_current_user
from crud.case import get_all_cases, get_case_by_id, get_case_stats, save_doctor_review
from models.review import DoctorReview
from models.user import User
from models.feedback import LabeledFeedback
from models.audit import AuditLog
from schemas.case import DiagnosisOut
from schemas.doctor import DoctorCaseOut, ReviewOut, ReviewRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/doctor", tags=["doctor"])

ISIC_CLASSES = ["MEL", "NV", "BCC", "AK", "BKL", "DF", "VASC", "SCC"]


# ── Role guard ────────────────────────────────────────────────────────────────

def _require_doctor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor access required",
        )
    return current_user


# ── Shared helper: Case → DoctorCaseOut ──────────────────────────────────────

def _to_doctor_case_out(case) -> DoctorCaseOut:
    symptoms = {
        "rapid_growth": case.symptom_rapid_growth,
        "bleeding": case.symptom_bleeding,
        "irregular_border": case.symptom_irregular_border,
        "itching": case.symptom_itching,
        "pain": case.symptom_pain,
    }

    result_out: Optional[DiagnosisOut] = None
    if case.result:
        r = case.result
        result_out = DiagnosisOut(
            predicted_class=r.predicted_class,
            description=r.description,
            confidence=r.confidence,
            is_high_risk=r.is_high_risk,
            all_probabilities=r.all_probabilities,
            urgency=r.urgency,
            urgency_reasons=r.urgency_reasons,
            urgency_score=r.urgency_score,
            agent_status=r.agent_status,
            agent_result=r.agent_result,
            rag_explanation=r.rag_explanation,
            rag_source=r.rag_source,
            gradcam_path=r.gradcam_path,
        )

    review_out: Optional[ReviewOut] = None
    if case.doctor_review:
        rev = case.doctor_review
        review_out = ReviewOut(
            doctor_id=rev.doctor_id,
            doctor_name=rev.doctor_name,
            decision=rev.decision,
            override_class=rev.override_class,
            notes=rev.notes,
            reviewed_at=rev.reviewed_at,
        )

    return DoctorCaseOut(
        id=str(case.id),
        user_id=case.user_id,
        image_filename=case.image_filename,
        created_at=case.created_at,
        symptoms=symptoms,
        result=result_out,
        doctor_review=review_out,
        lesion_id=case.lesion_id,
    )


# ── 0. Stats endpoint ────────────────────────────────────────────────────────

@router.get(
    "/stats",
    summary="Dashboard summary counts",
    response_description="Aggregate counts: total, urgency breakdown, pending review",
)
async def dashboard_stats(doctor: User = Depends(_require_doctor)):
    """
    Returns aggregate statistics for the doctor dashboard — avoids the frontend
    having to fetch all 500 cases just to display summary counts.

    Response shape:
    ```json
    {
      "total": 120,
      "high": 18,
      "medium": 42,
      "low": 60,
      "reviewed": 95,
      "pending_review": 25
    }
    ```
    """
    stats = await get_case_stats()
    logger.debug("dashboard_stats requested by Dr. %s: %s", doctor.full_name, stats)
    return stats


# ── 1. List all cases ─────────────────────────────────────────────────────────

@router.get(
    "/cases",
    response_model=list[DoctorCaseOut],
    summary="List all patient cases",
)
async def list_all_cases(
    urgency: Optional[str] = Query(default=None, description="Filter by urgency: HIGH | MEDIUM | LOW"),
    skip:    int           = Query(default=0,    ge=0,   description="Pagination offset"),
    limit:   int           = Query(default=50,   ge=1, le=200, description="Max records (1–200)"),
    doctor: User = Depends(_require_doctor),
):
    """
    Return all cases across all patients, newest first.
    Supports `?urgency=HIGH` filter and `?skip=0&limit=50` pagination.
    """
    cases = await get_all_cases(skip=skip, limit=limit, urgency=urgency)
    out = [_to_doctor_case_out(c) for c in cases]
    logger.debug("list_all_cases: skip=%d limit=%d urgency=%s count=%d", skip, limit, urgency, len(out))
    return out


# ── 2. Case detail ────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}", response_model=DoctorCaseOut)
async def get_case_detail(
    case_id: str,
    doctor: User = Depends(_require_doctor),
):
    """Return full case detail for any patient. Doctors can view all cases."""
    case = await get_case_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    await AuditLog(
        user_id=str(doctor.id),
        user_email=doctor.email,
        user_role=doctor.role,
        action="view",
        case_id=case_id,
    ).insert()

    return _to_doctor_case_out(case)


# ── 3. Submit review ──────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/review", response_model=DoctorCaseOut)
async def submit_review(
    case_id: str,
    body: ReviewRequest,
    doctor: User = Depends(_require_doctor),
):
    """
    Accept or override the AI diagnosis for a case.

    - decision == 'accepted'  : logs that the doctor agreed with AI prediction
    - decision == 'overridden': requires override_class — logs the doctor's own class

    Audit fields logged: doctor_id, doctor_name, decision, override_class, notes, reviewed_at
    """
    # Validate override
    if body.decision == "overridden":
        if not body.override_class:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="override_class is required when decision is 'overridden'",
            )
        if body.override_class.upper() not in ISIC_CLASSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"override_class must be one of: {ISIC_CLASSES}",
            )

    case = await get_case_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    review = DoctorReview(
        doctor_id=str(doctor.id),
        doctor_name=doctor.full_name,
        decision=body.decision,
        override_class=body.override_class.upper() if body.override_class else None,
        notes=body.notes,
        reviewed_at=datetime.now(timezone.utc),
    )

    updated = await save_doctor_review(case_id, review)
    
    # Store feedback for future model finetuning
    if body.decision == "overridden" and body.override_class:
        feedback = LabeledFeedback(
            case_id=str(case.id),
            doctor_id=str(doctor.id),
            ai_label=case.result.predicted_class if case.result else "UNKNOWN",
            doctor_label=body.override_class.upper()
        )
        await feedback.insert()

    await AuditLog(
        user_id=str(doctor.id),
        user_email=doctor.email,
        user_role=doctor.role,
        action="edit",
        case_id=case_id,
    ).insert()

    return _to_doctor_case_out(updated)


# ── 4. Generate PDF report ────────────────────────────────────────────────────

@router.get("/cases/{case_id}/report")
async def download_pdf_report(
    case_id: str,
    doctor: User = Depends(_require_doctor),
):
    """
    Generate and stream a PDF report for the given case.
    Uses reportlab. Download triggers automatically in the browser.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="reportlab not installed — run: pip install reportlab",
        )

    case = await get_case_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"], fontSize=18, spaceAfter=6, textColor=colors.HexColor("#1a1a2e")
    )
    heading_style = ParagraphStyle(
        "Heading", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#16213e"), spaceBefore=12
    )
    body_style = styles["BodyText"]
    small_style = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=9, textColor=colors.grey)

    # ── Urgency color ──────────────────────────────────────────────────────
    urgency_colors = {
        "HIGH": colors.HexColor("#dc2626"),
        "MEDIUM": colors.HexColor("#d97706"),
        "LOW": colors.HexColor("#16a34a"),
    }
    urgency = case.result.urgency if case.result else "UNKNOWN"
    urgency_color = urgency_colors.get(urgency, colors.grey)

    story = []

    # ── Header ────────────────────────────────────────────────────────────
    story.append(Paragraph("DermaAI — Case Report", title_style))
    story.append(Paragraph(
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
        f"&nbsp;|&nbsp; Case ID: <font color='grey'>{case_id}</font>",
        small_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb"), spaceAfter=10))

    # ── Patient & Submission ───────────────────────────────────────────────
    story.append(Paragraph("Patient & Submission", heading_style))
    story.append(Table(
        [
            ["Patient ID", case.user_id],
            ["Submitted", case.created_at.strftime("%Y-%m-%d %H:%M UTC")],
            ["Image File", case.image_filename],
        ],
        colWidths=[5 * cm, 13 * cm],
        style=TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]),
    ))

    # ── Symptoms ──────────────────────────────────────────────────────────
    story.append(Paragraph("Reported Symptoms", heading_style))
    symptom_map = {
        "Rapid Growth": case.symptom_rapid_growth,
        "Bleeding": case.symptom_bleeding,
        "Irregular Border": case.symptom_irregular_border,
        "Itching": case.symptom_itching,
        "Pain": case.symptom_pain,
    }
    symptom_rows = [[name, "YES" if val else "No"] for name, val in symptom_map.items()]
    story.append(Table(
        symptom_rows,
        colWidths=[8 * cm, 10 * cm],
        style=TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#dc2626")),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]),
    ))

    # ── AI Diagnosis ──────────────────────────────────────────────────────
    if case.result:
        r = case.result
        story.append(Paragraph("AI Diagnosis", heading_style))
        story.append(Table(
            [
                ["Predicted Class", f"{r.predicted_class} — {r.description}"],
                ["Confidence", f"{r.confidence:.1%}"],
                ["High Risk", "YES" if r.is_high_risk else "No"],
                ["Urgency", urgency],
                ["Urgency Reasons", "\n".join(r.urgency_reasons)],
                ["Agent Status", r.agent_status or "—"],
            ],
            colWidths=[5 * cm, 13 * cm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (1, 2), (1, 2), urgency_color),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]),
        ))

        # Agent explanation / referral message
        agent_text = None
        if r.agent_result:
            agent_text = (
                r.agent_result.get("explanation")
                or r.agent_result.get("referral_message")
                or r.agent_result.get("followup_questions")
            )
        if agent_text:
            story.append(Paragraph("AI Explanation", heading_style))
            story.append(Paragraph(agent_text, body_style))

        # RAG explanation
        if r.rag_explanation:
            story.append(Paragraph("RAG Knowledge Base Explanation", heading_style))
            story.append(Paragraph(r.rag_explanation, body_style))
            if r.rag_source:
                story.append(Paragraph(f"Source: {r.rag_source}", small_style))

    # ── Doctor Review ─────────────────────────────────────────────────────
    story.append(Paragraph("Doctor Review", heading_style))
    if case.doctor_review:
        rev = case.doctor_review
        effective_class = rev.override_class if rev.decision == "overridden" else (
            case.result.predicted_class if case.result else "—"
        )
        review_rows = [
            ["Reviewed By", f"Dr. {rev.doctor_name}"],
            ["Decision", rev.decision.upper()],
            ["Final Diagnosis", effective_class],
            ["Notes", rev.notes or "—"],
            ["Reviewed At", rev.reviewed_at.strftime("%Y-%m-%d %H:%M UTC")],
        ]
        story.append(Table(
            review_rows,
            colWidths=[5 * cm, 13 * cm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f0fdf4"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]),
        ))
    else:
        story.append(Paragraph("No doctor review recorded for this case.", body_style))

    # ── Footer disclaimer ─────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "DISCLAIMER: This report is generated by an AI-assisted diagnostic system. "
        "It must be reviewed and confirmed by a qualified dermatologist before any "
        "clinical decisions are made. This system does not replace professional medical judgment.",
        small_style,
    ))

    doc.build(story)
    buf.seek(0)

    filename = f"dermaai_case_{case_id[:8]}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── 5. Export labeled feedback ────────────────────────────────────────────────

@router.get("/feedback/export")
async def export_feedback(doctor: User = Depends(_require_doctor)):
    """
    Export doctor overrides as a CSV for future model finetuning.
    Returns: case_id, doctor_id, ai_label, doctor_label, timestamp
    """
    feedback_records = await LabeledFeedback.find_all().to_list()
    
    output = io.StringIO()
    output.write("case_id,doctor_id,ai_label,doctor_label,timestamp\n")
    for f in feedback_records:
        ts = f.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        output.write(f"{f.case_id},{f.doctor_id},{f.ai_label},{f.doctor_label},{ts}\n")
        
    buf = io.BytesIO(output.getvalue().encode('utf-8'))
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="doctor_feedback.csv"'}
    )
