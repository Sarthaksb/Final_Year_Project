"""
backend/api/routes/lesions.py
-----------------------------
Endpoints for lesion tracking (Phase 11C).
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.dependencies import get_current_user
from models.case import Case
from models.lesion import Lesion
from models.user import User

router = APIRouter(prefix="/lesions", tags=["lesions"])


class LesionCreate(BaseModel):
    body_site: str
    label: str


@router.post("", response_model=Lesion)
async def create_lesion(data: LesionCreate, user: User = Depends(get_current_user)):
    """Create a new tracked lesion for the current patient."""
    lesion = Lesion(patient_id=str(user.id), body_site=data.body_site, label=data.label)
    await lesion.insert()
    return lesion


@router.get("")
async def get_lesions(user: User = Depends(get_current_user)):
    """Get all lesions tracked by the current patient."""
    lesions = await Lesion.find(Lesion.patient_id == str(user.id)).to_list()
    return lesions


@router.get("/{lesion_id}/timeline")
async def get_lesion_timeline(lesion_id: str, user: User = Depends(get_current_user)):
    """
    Get the longitudinal timeline for a specific lesion.
    Returns cases ordered by created_at.
    """
    lesion = await Lesion.get(lesion_id)
    if not lesion:
        raise HTTPException(status_code=404, detail="Lesion not found")
        
    # Doctor can view any patient's lesion, patient can only view their own
    if user.role != "doctor" and lesion.patient_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    cases = await Case.find(Case.lesion_id == lesion_id).sort(+Case.created_at).to_list()
    
    timeline = []
    for i, case in enumerate(cases):
        curr_score = 0
        score_diff = 0
        changed_flag = False
        if case.result:
            p = case.result.all_probabilities
            curr_score = p.get("MEL", 0) + p.get("BCC", 0) + p.get("SCC", 0)
            
            if i > 0 and cases[i-1].result:
                prev_p = cases[i-1].result.all_probabilities
                prev_score = prev_p.get("MEL", 0) + prev_p.get("BCC", 0) + prev_p.get("SCC", 0)
                score_diff = curr_score - prev_score
                if score_diff >= 0.15:
                    changed_flag = True

        timeline.append({
            "case_id": str(case.id),
            "created_at": case.created_at,
            "image_filename": case.image_filename,
            "predicted_class": case.result.predicted_class if case.result else None,
            "confidence": case.result.confidence if case.result else None,
            "malignancy_score": curr_score,
            "score_diff": score_diff,
            "changed_flag": changed_flag,
            "urgency": case.result.urgency if case.result else None,
        })
        
    return {"lesion": lesion, "timeline": timeline}
