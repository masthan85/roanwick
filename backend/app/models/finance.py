import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin
from app.models.identity import pk


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    id: Mapped[uuid.UUID] = pk()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider_name: Mapped[str] = mapped_column(String(20))  # sandbox | stripe
    external_id: Mapped[str] = mapped_column(String(100), unique=True)
    amount_pence: Mapped[int] = mapped_column(Integer)
    credit_applied_pence: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    status: Mapped[str] = mapped_column(String(20), default="requires_payment")
    # requires_payment | processing | succeeded | failed | refunded | partially_refunded
    failure_message: Mapped[str | None] = mapped_column(String(200))
    client_secret: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    processing_fee_pence: Mapped[int | None] = mapped_column(Integer)
    processing_fee_source: Mapped[str] = mapped_column(String(10), default="estimated")  # actual | estimated
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Refund(Base, TimestampMixin):
    __tablename__ = "refunds"
    id: Mapped[uuid.UUID] = pk()
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"), index=True)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), index=True)
    amount_pence: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(30))  # cancellation | complaint | goodwill | provider_cancelled | other
    funded_by: Mapped[str] = mapped_column(String(20), default="customer_policy")  # customer_policy | platform | provider
    external_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending | succeeded | failed
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class RefundRequest(Base, TimestampMixin):
    __tablename__ = "refund_requests"
    id: Mapped[uuid.UUID] = pk()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    requested_pence: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(12), default="open")  # open | approved | rejected
    approved_pence: Mapped[int | None] = mapped_column(Integer)
    decision_note: Mapped[str | None] = mapped_column(String(500))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Payout(Base, TimestampMixin):
    __tablename__ = "payouts"
    __table_args__ = (UniqueConstraint("booking_id", name="uq_payout_booking"),)
    id: Mapped[uuid.UUID] = pk()
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("provider_profiles.user_id"), index=True)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"))
    gross_pence: Mapped[int] = mapped_column(Integer)  # service value the commission was charged on
    commission_pence: Mapped[int] = mapped_column(Integer)
    amount_pence: Mapped[int] = mapped_column(Integer)  # net to provider
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending | released | paid | failed | cancelled | held
    release_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    external_id: Mapped[str | None] = mapped_column(String(100))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(200))


class BookingFinancial(Base, TimestampMixin):
    """Per-booking economics, written when a booking is finalised (completed, or cancelled with retained fees)."""

    __tablename__ = "booking_financials"
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), primary_key=True)
    gross_paid_pence: Mapped[int] = mapped_column(Integer, default=0)  # cash taken from customer
    credit_used_pence: Mapped[int] = mapped_column(Integer, default=0)
    service_value_pence: Mapped[int] = mapped_column(Integer, default=0)  # basis for commission
    fee_pence: Mapped[int] = mapped_column(Integer, default=0)
    promo_cost_pence: Mapped[int] = mapped_column(Integer, default=0)
    commission_bps: Mapped[int] = mapped_column(Integer, default=0)
    commission_pence: Mapped[int] = mapped_column(Integer, default=0)
    provider_earning_pence: Mapped[int] = mapped_column(Integer, default=0)
    processing_fee_pence: Mapped[int] = mapped_column(Integer, default=0)
    processing_fee_source: Mapped[str] = mapped_column(String(10), default="estimated")
    refunded_pence: Mapped[int] = mapped_column(Integer, default=0)
    platform_funded_refund_pence: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str] = mapped_column(String(20), default="completed")  # completed | late_cancelled
    outward_code: Mapped[str] = mapped_column(String(5))
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_offerings.id"))
    finalised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BusinessCost(Base, TimestampMixin):
    """Manually entered operating costs. Reported separately from transaction data and labelled as manual."""

    __tablename__ = "business_costs"
    id: Mapped[uuid.UUID] = pk()
    category: Mapped[str] = mapped_column(String(30))  # marketing | support | insurance | tools | other
    channel: Mapped[str | None] = mapped_column(String(40))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    amount_pence: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(200))
    entered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ProviderAdjustment(Base, TimestampMixin):
    """Money a professional owes the platform, for example a refund they funded after their payout was already paid.
    It is netted off their next payouts."""

    __tablename__ = "provider_adjustments"
    id: Mapped[uuid.UUID] = pk()
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("provider_profiles.user_id"), index=True)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"))
    owed_pence: Mapped[int] = mapped_column(Integer)
    remaining_pence: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(200))
