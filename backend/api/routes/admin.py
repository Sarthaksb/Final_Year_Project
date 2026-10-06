from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from api.dependencies import require_admin
from models.user import User
from models.case import Case
from models.audit import AuditLog
from models.feedback import LabeledFeedback

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/analytics")
async def get_analytics(admin: User = Depends(require_admin)):
    cases = await Case.find_all().to_list()
    
    # Cases per day (last 7 days)
    now = datetime.now(timezone.utc)
    cases_per_day = {}
    for i in range(7):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        cases_per_day[d] = 0
        
    urgency_distribution = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    agreement = {"agreed": 0, "overridden": 0}
    review_times = []
    override_per_class = {}
    total_overrides = 0
    
    for c in cases:
        d = c.created_at.strftime("%Y-%m-%d")
        if d in cases_per_day:
            cases_per_day[d] += 1
            
        if c.result:
            urgency = c.result.urgency
            if urgency in urgency_distribution:
                urgency_distribution[urgency] += 1
                
        if c.doctor_review:
            if c.doctor_review.decision == "accepted":
                agreement["agreed"] += 1
            else:
                agreement["overridden"] += 1
                total_overrides += 1
                ovr_cls = c.doctor_review.override_class
                if ovr_cls:
                    override_per_class[ovr_cls] = override_per_class.get(ovr_cls, 0) + 1
                    
            rev_time = (c.doctor_review.reviewed_at - c.created_at).total_seconds() / 3600 # hours
            review_times.append(rev_time)
            
    avg_review_time = sum(review_times) / len(review_times) if review_times else 0
    
    # Format charts
    cases_per_day_chart = [{"date": k, "cases": v} for k, v in sorted(cases_per_day.items())]
    urgency_chart = [{"name": k, "value": v} for k, v in urgency_distribution.items()]
    agreement_chart = [{"name": "Agreed", "value": agreement["agreed"]}, {"name": "Overridden", "value": agreement["overridden"]}]
    override_class_chart = [{"name": k, "value": v} for k, v in override_per_class.items()]
    
    return {
        "cases_per_day": cases_per_day_chart,
        "urgency_distribution": urgency_chart,
        "agreement": agreement_chart,
        "override_per_class": override_class_chart,
        "avg_review_time_hours": avg_review_time,
        "total_cases": len(cases),
        "total_overrides": total_overrides
    }

@router.get("/audit")
async def get_audit_logs(admin: User = Depends(require_admin), limit: int = 100):
    logs = await AuditLog.find_all().sort("-timestamp").limit(limit).to_list()
    return logs
