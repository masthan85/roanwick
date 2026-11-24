"""Management reporting. Every figure is tagged so readers can tell actual transaction data from
estimates and from manually entered costs. Gross booking value is reported separately and is not revenue."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models.bookings import Booking
from app.models.catalogue import ServiceOffering
from app.models.engagement import Complaint, Review
from app.models.finance import BookingFinancial, BusinessCost, Payment, Payout, Refund, RefundRequest
from app.models.identity import CustomerProfile
from app.models.providers import ProviderDocument, ProviderProfile
from app.models.system import MetricEvent
from app.services.config_store import get_setting

ACTUAL, ESTIMATE, MANUAL = "actual", "estimated", "manual"


def _window(start: date, end: date) -> tuple[datetime, datetime]:
    return (datetime.combine(start, time.min, tzinfo=timezone.utc), datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc))


def _m(value, basis, note=None):
    return {"value": value, "basis": basis, **({"note": note} if note else {})}


def finance_report(db: Session, start: date, end: date) -> dict:
    lo, hi = _window(start, end)
    paid = db.execute(
        select(func.coalesce(func.sum(Payment.amount_pence), 0), func.coalesce(func.sum(Payment.credit_applied_pence), 0), func.count())
        .where(Payment.paid_at >= lo, Payment.paid_at < hi)
    ).one()
    gbv = paid[0] + paid[1]

    f = BookingFinancial
    agg = db.execute(
        select(
            func.count(), func.coalesce(func.sum(f.service_value_pence), 0), func.coalesce(func.sum(f.commission_pence), 0),
            func.coalesce(func.sum(f.fee_pence), 0), func.coalesce(func.sum(f.promo_cost_pence), 0),
            func.coalesce(func.sum(f.provider_earning_pence), 0),
            func.coalesce(func.sum(case((f.processing_fee_source == "actual", f.processing_fee_pence), else_=0)), 0),
            func.coalesce(func.sum(case((f.processing_fee_source != "actual", f.processing_fee_pence), else_=0)), 0),
            func.coalesce(func.sum(f.platform_funded_refund_pence), 0),
        ).where(f.finalised_at >= lo, f.finalised_at < hi)
    ).one()
    n, service_value, commission, fees, promo, earnings, proc_actual, proc_est, plat_refunds = agg
    revenue = commission + fees - promo
    processing = proc_actual + proc_est
    contribution = revenue - processing - plat_refunds

    refunds_total = db.scalar(select(func.coalesce(func.sum(Refund.amount_pence), 0)).where(Refund.created_at >= lo, Refund.created_at < hi, Refund.status != "failed"))
    payouts_paid = db.scalar(select(func.coalesce(func.sum(Payout.amount_pence), 0)).where(Payout.paid_at >= lo, Payout.paid_at < hi, Payout.status == "paid"))
    payouts_owed = db.scalar(select(func.coalesce(func.sum(Payout.amount_pence), 0)).where(Payout.status.in_(("pending", "held"))))

    costs = {c: v for c, v in db.execute(select(BusinessCost.category, func.sum(BusinessCost.amount_pence)).where(BusinessCost.period_start >= start, BusinessCost.period_start <= end).group_by(BusinessCost.category))}
    marketing = costs.get("marketing", 0)

    first_paid = (
        select(Payment.customer_id, func.min(Payment.paid_at).label("first")).where(Payment.status.in_(("succeeded", "refunded", "partially_refunded"))).group_by(Payment.customer_id).subquery()
    )
    new_customers = db.scalar(select(func.count()).select_from(first_paid).where(first_paid.c.first >= lo, first_paid.c.first < hi))

    per_cust = db.execute(select(Booking.customer_id, func.count().label("c")).where(Booking.status == "completed", Booking.completed_at < hi).group_by(Booking.customer_id)).all()
    cust_n = len(per_cust)
    repeat_n = sum(1 for _, c in per_cust if c >= 2)
    repeat_rate = round(repeat_n / cust_n, 3) if cust_n else None
    contrib_per_booking = round(contribution / n) if n else None
    if cust_n >= 20:
        expected, basis_note = round(sum(c for _, c in per_cust) / cust_n, 2), "Observed average completed bookings per customer."
    else:
        expected, basis_note = float(get_setting(db, "assumed_visits_per_year")), "Fewer than 20 customers with completed bookings, so this uses the configured assumed visits per year."
    ltv = round(contrib_per_booking * expected) if contrib_per_booking is not None else None

    def breakdown(col, label_fn):
        rows = db.execute(
            select(col, func.count(), func.sum(f.service_value_pence), func.sum(f.commission_pence + f.fee_pence - f.promo_cost_pence),
                   func.sum(f.commission_pence + f.fee_pence - f.promo_cost_pence - f.processing_fee_pence - f.platform_funded_refund_pence))
            .where(f.finalised_at >= lo, f.finalised_at < hi).group_by(col)
        ).all()
        return [{"key": label_fn(k), "bookings": c, "service_value_pence": int(sv or 0), "revenue_pence": int(rev or 0), "contribution_pence": int(con or 0)} for k, c, sv, rev, con in rows]

    names = {o.id: o.name for o in db.scalars(select(ServiceOffering))}
    return {
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "gross_booking_value": _m(gbv, ACTUAL, "Cash and credit taken from customers. This is not company revenue."),
        "payments_taken": _m(paid[2], ACTUAL),
        "finalised_bookings": _m(n, ACTUAL),
        "service_value": _m(int(service_value), ACTUAL, "Commission basis: labour, add-ons and plan discounts."),
        "platform_revenue": _m(int(revenue), ACTUAL, "Commission plus customer booking fees, less platform-funded promotions."),
        "commission": _m(int(commission), ACTUAL),
        "booking_fees": _m(int(fees), ACTUAL),
        "promotion_cost": _m(int(promo), ACTUAL),
        "provider_earnings": _m(int(earnings), ACTUAL, "Earned on finalised bookings. Cash paid out is shown separately."),
        "provider_payouts_paid": _m(int(payouts_paid), ACTUAL),
        "provider_payouts_owed": _m(int(payouts_owed), ACTUAL, "Liability at the end of the period, not limited to the window."),
        "processing_costs": _m(int(processing), ACTUAL if proc_est == 0 and processing else ESTIMATE,
                               f"£{proc_actual / 100:.2f} from processor data, £{proc_est / 100:.2f} estimated from configured rates."),
        "refunds_issued": _m(int(refunds_total), ACTUAL),
        "platform_funded_refunds": _m(int(plat_refunds), ACTUAL, "Goodwill and fault refunds paid for by the platform."),
        "contribution": _m(int(contribution), ESTIMATE if proc_est else ACTUAL, "Revenue less processing costs and platform-funded refunds. Excludes marketing, support and overheads."),
        "contribution_per_booking": _m(contrib_per_booking, ESTIMATE if proc_est else ACTUAL),
        "manual_costs": {"basis": MANUAL, "by_category": {k: int(v) for k, v in costs.items()}, "note": "Entered by staff. Not from transactions."},
        "new_paying_customers": _m(new_customers, ACTUAL),
        "customer_acquisition_cost": _m(
            round(marketing / new_customers) if (new_customers and marketing) else None, MANUAL,
            "Manually entered marketing spend divided by new paying customers in the period." if marketing else "Not available: no marketing spend has been entered for this period.",
        ),
        "repeat_booking_rate": _m(repeat_rate, ACTUAL, f"{repeat_n} of {cust_n} customers with a completed booking have booked at least twice."),
        "lifetime_value_estimate": _m(ltv, ESTIMATE, f"Contribution per booking times {expected} expected bookings. {basis_note}"),
        "by_service": breakdown(f.offering_id, lambda k: names.get(k, str(k))),
        "by_area": breakdown(f.outward_code, lambda k: k),
    }


def operations_report(db: Session, start: date, end: date) -> dict:
    lo, hi = _window(start, end)
    statuses = dict(db.execute(select(Booking.status, func.count()).where(Booking.created_at >= lo, Booking.created_at < hi).group_by(Booking.status)).all())
    cancelled_by = dict(db.execute(select(Booking.cancelled_by, func.count()).where(Booking.created_at >= lo, Booking.created_at < hi, Booking.status == "cancelled").group_by(Booking.cancelled_by)).all())
    real = sum(v for k, v in statuses.items() if k not in ("expired", "pending_payment"))
    started = db.scalar(select(func.count()).select_from(Booking).where(Booking.started_at >= lo, Booking.started_at < hi))
    late = db.scalar(select(func.count()).select_from(Booking).where(Booking.started_at >= lo, Booking.started_at < hi, Booking.arrived_late.is_(True)))
    completed = statuses.get("completed", 0)
    complaints = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.created_at >= lo, Complaint.created_at < hi))
    sla = int(get_setting(db, "complaint_sla_hours"))
    breached = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.first_response_at.is_(None), Complaint.status.in_(("open", "investigating")), Complaint.created_at < utcnow() - timedelta(hours=sla)))
    avg_rating = db.scalar(select(func.avg(Review.rating)).where(Review.created_at >= lo, Review.created_at < hi))
    provs = dict(db.execute(select(ProviderProfile.status, func.count()).group_by(ProviderProfile.status)).all())
    expiring = db.scalar(select(func.count()).select_from(ProviderDocument).where(ProviderDocument.status == "approved", ProviderDocument.expires_on.is_not(None), ProviderDocument.expires_on <= date.today() + timedelta(days=30)))
    from app.models.engagement import SupportTicket

    quality_open = db.scalar(select(func.count()).select_from(SupportTicket).where(SupportTicket.kind == "quality_review", SupportTicket.status != "closed"))
    unassigned = db.scalar(select(func.count()).select_from(Booking).where(Booking.provider_id.is_(None), Booking.status == "awaiting_provider"))
    return {
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "bookings_by_status": statuses, "cancelled_by": {k or "unknown": v for k, v in cancelled_by.items()},
        "cancellation_rate": None if not real else round(statuses.get("cancelled", 0) / real, 3),
        "provider_cancellation_rate": None if not real else round(cancelled_by.get("provider", 0) / real, 3),
        "on_time_rate": None if not started else round(1 - late / started, 3),
        "complaints": complaints, "complaints_per_100_completed": None if not completed else round(complaints * 100 / completed, 1),
        "complaints_past_sla": breached, "average_rating": round(float(avg_rating), 2) if avg_rating else None,
        "providers_by_status": provs, "quality_reviews_open": quality_open, "documents_expiring_30_days": expiring, "unassigned_bookings": unassigned,
        "open_refund_requests": db.scalar(select(func.count()).select_from(RefundRequest).where(RefundRequest.status == "open")),
    }


def growth_report(db: Session, start: date, end: date) -> dict:
    lo, hi = _window(start, end)
    signups = dict(db.execute(select(CustomerProfile.acquisition_source, func.count()).where(CustomerProfile.created_at >= lo, CustomerProfile.created_at < hi).group_by(CustomerProfile.acquisition_source)).all())
    paying = dict(db.execute(
        select(CustomerProfile.acquisition_source, func.count(func.distinct(Payment.customer_id)))
        .join(Payment, Payment.customer_id == CustomerProfile.user_id).where(Payment.status.in_(("succeeded", "refunded", "partially_refunded")), CustomerProfile.created_at >= lo, CustomerProfile.created_at < hi)
        .group_by(CustomerProfile.acquisition_source)).all())
    spend = dict(db.execute(select(BusinessCost.channel, func.sum(BusinessCost.amount_pence)).where(BusinessCost.category == "marketing", BusinessCost.period_start >= start, BusinessCost.period_start <= end).group_by(BusinessCost.channel)).all())
    channels = []
    for ch in sorted(set(signups) | set(spend)):
        s, p, c = signups.get(ch, 0), paying.get(ch, 0), int(spend.get(ch, 0) or 0)
        channels.append({"channel": ch or "unattributed", "signups": s, "paying_customers": p, "conversion": round(p / s, 3) if s else None, "marketing_spend_pence": c, "spend_basis": MANUAL, "cac_pence": round(c / p) if p and c else None})
    q = db.scalar(select(func.count()).select_from(MetricEvent).where(MetricEvent.name == "quote_created", MetricEvent.at >= lo, MetricEvent.at < hi))
    created = db.scalar(select(func.count()).select_from(Booking).where(Booking.created_at >= lo, Booking.created_at < hi))
    paid = db.scalar(select(func.count()).select_from(Booking).where(Booking.created_at >= lo, Booking.created_at < hi, Booking.status.notin_(("pending_payment", "expired"))))
    done = db.scalar(select(func.count()).select_from(Booking).where(Booking.created_at >= lo, Booking.created_at < hi, Booking.status == "completed"))
    waitlist = db.scalar(select(func.count()).select_from(MetricEvent).where(MetricEvent.name == "waitlist_signup", MetricEvent.at >= lo, MetricEvent.at < hi))

    # Retention: customers grouped by the month of their first completed booking.
    rows = db.execute(select(Booking.customer_id, Booking.completed_at).where(Booking.status == "completed").order_by(Booking.customer_id, Booking.completed_at)).all()
    per: dict = defaultdict(list)
    for cid, at in rows:
        per[cid].append(at)
    cohorts: dict[str, dict] = {}
    for dates in per.values():
        first = dates[0]
        key = first.strftime("%Y-%m")
        c = cohorts.setdefault(key, {"customers": 0, "d30": 0, "d60": 0, "d90": 0})
        c["customers"] += 1
        for label, days in (("d30", 30), ("d60", 60), ("d90", 90)):
            if any(first < d <= first + timedelta(days=days) for d in dates[1:]):
                c[label] += 1
    cohort_rows = [{"cohort": k, **v, **{f"{x}_rate": round(v[x] / v["customers"], 3) for x in ("d30", "d60", "d90")}} for k, v in sorted(cohorts.items())]
    return {
        "period": {"from": start.isoformat(), "to": end.isoformat()}, "acquisition_by_channel": channels,
        "funnel": {"quotes": q, "bookings_started": created, "bookings_paid": paid, "bookings_completed": done, "waitlist_signups": waitlist},
        "retention_cohorts": cohort_rows,
        "note": "Retention rates only mean something once cohorts have had time to mature. Treat small cohorts as anecdotes.",
    }
