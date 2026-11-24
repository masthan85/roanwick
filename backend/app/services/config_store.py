"""Business configuration. Commercial assumptions live in the database, never in code paths."""
from sqlalchemy.orm import Session

from app.models.system import AppSetting, FeatureFlag

DEFAULT_SETTINGS: dict[str, tuple[object, str]] = {
    "commission_bps": (2200, "Platform commission on service value, in basis points (2200 = 22%)."),
    "customer_booking_fee_pence": (0, "Flat customer-facing booking fee in pence. Shown in every quote."),
    "payout_hold_days": (3, "Days after completion before a provider payout is released."),
    "cancellation_tiers": (
        [
            {"hours_before": 48, "refund_bps": 10000},
            {"hours_before": 24, "refund_bps": 5000},
            {"hours_before": 0, "refund_bps": 0},
        ],
        "Customer cancellation refund tiers. First tier whose hours_before is met applies.",
    ),
    "provider_cancellation_penalty_after": (2, "Provider cancellations in a rolling month before an automatic review."),
    "hold_minutes": (15, "Minutes a slot is held while the customer pays."),
    "min_notice_hours": (12, "Minimum notice for a new booking."),
    "booking_horizon_days": (60, "How far ahead customers can book."),
    "provider_acceptance_hours": (4, "Hours a provider has to accept a request before it is re-matched."),
    "processing_fee_bps": (150, "Estimated card processing fee percentage in basis points (assumption until actuals arrive)."),
    "processing_fee_fixed_pence": (20, "Estimated fixed card processing fee per charge in pence."),
    "referral_reward_pence": (1000, "Credit for the referrer after the referred customer's first completed booking."),
    "referral_welcome_pence": (1000, "Credit for the referred customer after their first completed booking."),
    "document_expiry_reminder_days": (30, "Days before expiry that providers are reminded."),
    "complaint_sla_hours": (48, "Target hours to first response on a complaint."),
    "quote_valid_minutes": (60, "How long a quotation stays valid."),
    "prices_include_vat": (True, "Display flag only. VAT treatment requires accountant review before launch."),
    "plan_horizon_days": (8, "How many days ahead recurring-plan visits are scheduled and charged. Keep short so customers are not charged weeks early."),
    "require_staff_mfa": (False, "When on, staff without two-step verification are blocked from admin actions until they enrol."),
    "quality_cancel_threshold": (3, "Withdrawals from confirmed jobs that trigger a quality review of a professional."),
    "quality_late_rate_pct": (25, "Share of started jobs that were late (percent) that triggers a quality review, once at least 4 jobs are done."),
    "quality_min_rating": (3.5, "Average rating below this, with at least 5 reviews, triggers a quality review."),
    "assumed_visits_per_year": (14, "Assumed repeat visits per customer per year for lifetime value estimates until observed data exists."),
}

DEFAULT_FLAGS: dict[str, tuple[bool, str]] = {
    "recurring_plans": (True, "Allow customers to set up weekly or fortnightly plans."),
    "referrals": (True, "Enable referral codes and credit."),
    "promotions": (True, "Enable promotional codes."),
    "customer_chooses_provider": (True, "Let customers pick a specific professional rather than automatic matching only."),
    "provider_self_signup": (True, "Allow new providers to start onboarding."),
    "maintenance_bundles": (False, "Home care plans for maintenance. Off until trade compliance is defined."),
}


def ensure_defaults(db: Session) -> None:
    existing = {s.key for s in db.query(AppSetting.key)}
    for k, (v, d) in DEFAULT_SETTINGS.items():
        if k not in existing:
            db.add(AppSetting(key=k, value=v, description=d))
    existing_f = {f.key for f in db.query(FeatureFlag.key)}
    for k, (v, d) in DEFAULT_FLAGS.items():
        if k not in existing_f:
            db.add(FeatureFlag(key=k, enabled=v, description=d))
    db.flush()


def get_setting(db: Session, key: str):
    row = db.get(AppSetting, key)
    if row is not None:
        return row.value
    return DEFAULT_SETTINGS[key][0]


def flag(db: Session, key: str) -> bool:
    row = db.get(FeatureFlag, key)
    return row.enabled if row is not None else DEFAULT_FLAGS.get(key, (False, ""))[0]
