"""
backend/crud/case.py
---------------------
CRUD operations for the Case collection via Beanie.

Functions
---------
create_case           — insert new case
get_cases_by_user     — paginated patient history
get_case_by_id        — single case lookup
get_all_cases         — paginated list (doctor view)
save_doctor_review    — attach doctor review to case
delete_case           — hard-delete case + image file
get_case_stats        — aggregate urgency/review counts (doctor dashboard)
"""

import logging
from pathlib import Path
from typing import Optional

from beanie import PydanticObjectId

from models.case import Case
from models.diagnosis import DiagnosisResult

logger = logging.getLogger(__name__)


# ── Create ────────────────────────────────────────────────────────────────────

async def create_case(
    user_id:        str,
    image_filename: str,
    image_path:     str,
    symptoms:       dict,
    result:         Optional[DiagnosisResult] = None,
    lesion_id:      Optional[str] = None,
) -> Case:
    """Insert a new Case document and return it."""
    case = Case(
        user_id               = user_id,
        image_filename        = image_filename,
        image_path            = image_path,
        symptom_rapid_growth  = symptoms.get("rapid_growth",    False),
        symptom_bleeding      = symptoms.get("bleeding",        False),
        symptom_irregular_border = symptoms.get("irregular_border", False),
        symptom_itching       = symptoms.get("itching",         False),
        symptom_pain          = symptoms.get("pain",            False),
        result                = result,
        lesion_id             = lesion_id,
    )
    await case.insert()
    logger.debug("Case inserted: %s", case.id)
    return case


# ── Read ──────────────────────────────────────────────────────────────────────

async def get_cases_by_user(
    user_id: str,
    skip:    int = 0,
    limit:   int = 50,
) -> list[Case]:
    """
    Return cases belonging to a user, newest first.
    Supports pagination via skip/limit.
    """
    return (
        await Case.find(Case.user_id == user_id)
        .sort(-Case.created_at)
        .skip(skip)
        .limit(limit)
        .to_list()
    )


async def count_cases_by_user(user_id: str) -> int:
    """Total number of cases for a given user."""
    return await Case.find(Case.user_id == user_id).count()


async def get_case_by_id(case_id: str) -> Optional[Case]:
    """Return a single case by its string ObjectId, or None."""
    try:
        oid = PydanticObjectId(case_id)
    except Exception:
        return None
    return await Case.get(oid)


async def get_all_cases(
    skip:    int = 0,
    limit:   int = 50,
    urgency: Optional[str] = None,
) -> list[Case]:
    """
    Return cases across all patients, newest first.
    Supports pagination and optional urgency filter.
    Used by the doctor dashboard.
    """
    # Build filter condition
    query = Case.find()
    # Urgency is stored inside the embedded result document
    # We filter in Python (simpler with Beanie; for large datasets use a native Motor pipeline)
    all_cases = await query.sort(-Case.created_at).skip(skip).limit(limit).to_list()
    if urgency:
        urgency_upper = urgency.upper()
        all_cases = [c for c in all_cases if c.result and c.result.urgency == urgency_upper]
    return all_cases


async def count_all_cases() -> int:
    """Total number of cases across all patients."""
    return await Case.find().count()


async def get_case_stats() -> dict:
    """
    Aggregate case statistics for the doctor dashboard.
    Returns counts for urgency levels and review status.

    Example response:
        {
          "total": 120,
          "high": 18,
          "medium": 42,
          "low": 60,
          "reviewed": 95,
          "pending_review": 25,
        }
    """
    all_cases = await Case.find_all().to_list()
    total    = len(all_cases)
    high     = sum(1 for c in all_cases if c.result and c.result.urgency == "HIGH")
    medium   = sum(1 for c in all_cases if c.result and c.result.urgency == "MEDIUM")
    low      = sum(1 for c in all_cases if c.result and c.result.urgency == "LOW")
    reviewed = sum(1 for c in all_cases if c.doctor_review is not None)

    return {
        "total":          total,
        "high":           high,
        "medium":         medium,
        "low":            low,
        "reviewed":       reviewed,
        "pending_review": total - reviewed,
    }


# ── Update ────────────────────────────────────────────────────────────────────

async def save_doctor_review(case_id: str, review) -> Optional[Case]:
    """
    Attach a DoctorReview to an existing Case document.

    Args:
        case_id : string ObjectId of the case
        review  : DoctorReview instance

    Returns:
        Updated Case document, or None if case not found.
    """
    case = await get_case_by_id(case_id)
    if case is None:
        return None
    case.doctor_review = review
    await case.save()
    logger.info("Doctor review saved for case %s", case_id)
    return case


# ── Delete ────────────────────────────────────────────────────────────────────

async def delete_case(case_id: str, upload_dir: str = "uploads") -> bool:
    """
    Hard-delete a case document from MongoDB and remove its image file from disk.

    Args:
        case_id    : string ObjectId of the case
        upload_dir : base directory where images are stored

    Returns:
        True if deleted, False if case not found.
    """
    case = await get_case_by_id(case_id)
    if case is None:
        return False

    # Delete image file
    image_path = Path(upload_dir) / case.image_filename
    if image_path.exists():
        try:
            image_path.unlink()
            logger.info("Deleted image file: %s", image_path)
        except Exception as exc:
            logger.warning("Could not delete image %s: %s", image_path, exc)

    await case.delete()
    logger.info("Case %s deleted from MongoDB", case_id)
    return True
