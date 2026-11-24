"""Quality management. Thresholds are settings. Tripping one opens a review ticket for operations: nothing is suspended automatically,
because a person should look at the context before a professional loses work."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models.engagement import Complaint, SupportTicket
from app.models.identity import AuditEvent
from app.models.providers import ProviderProfile
from app.services.config_store import get_setting


def concerns(db: Session, p: ProviderProfile) -> list[str]:
    out = []
    cancel_limit = int(get_setting(db, "quality_cancel_threshold"))
    if cancel_limit and p.cancel_count >= cancel_limit:
        out.append(f"{p.cancel_count} withdrawals from confirmed jobs")
    started = p.jobs_completed
    late_pct = float(get_setting(db, "quality_late_rate_pct"))
    if started >= 4 and p.late_count * 100 / started >= late_pct:
        out.append(f"{p.late_count} late starts in {started} jobs")
    min_rating = float(get_setting(db, "quality_min_rating"))
    if p.rating_count >= 5 and float(p.rating_avg) < min_rating:
        out.append(f"average rating {float(p.rating_avg):.2f} from {p.rating_count} reviews")
    serious = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.provider_id == p.user_id, Complaint.severity == "high"))
    if serious >= 2:
        out.append(f"{serious} high-severity complaints")
    return out


def evaluate(db: Session, provider_id) -> SupportTicket | None:
    p = db.get(ProviderProfile, provider_id)
    if p is None or p.status != "approved":
        return None
    reasons = concerns(db, p)
    if not reasons:
        return None
    open_review = db.scalar(select(SupportTicket.id).where(SupportTicket.user_id == provider_id, SupportTicket.kind == "quality_review", SupportTicket.status != "closed"))
    if open_review:
        return None
    t = SupportTicket(
        user_id=provider_id, kind="quality_review", subject=f"Quality review: {p.display_name}",
        body="Opened automatically because: " + "; ".join(reasons) + ". Review their record and decide whether to coach, restrict or suspend. Nothing has been changed automatically.",
    )
    db.add(t)
    db.add(AuditEvent(at=utcnow(), action="quality.review_opened", entity_type="provider", entity_id=str(provider_id), after={"reasons": reasons}))
    db.flush()
    return t
