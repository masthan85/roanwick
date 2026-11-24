import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.models.identity import pk

# Statuses that occupy a professional's time. Kept in one place and mirrored in the exclusion constraint.
BLOCKING_STATUSES = ("pending_payment", "awaiting_provider", "confirmed", "in_progress")


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at"),
        CheckConstraint("blocked_until >= ends_at"),
        UniqueConstraint("customer_id", "idempotency_key", name="uq_booking_customer_idem"),
        # Database-level protection against double-booking a professional, whatever the application does.
        ExcludeConstraint(
            ("provider_id", "="),
            (func.tstzrange(text("starts_at"), text("blocked_until"), "[)"), "&&"),
            where=text("provider_id is not null and status in ('pending_payment','awaiting_provider','confirmed','in_progress')"),
            using="gist",
            name="bookings_no_provider_overlap",
        ),
    )
    id: Mapped[uuid.UUID] = pk()
    reference: Mapped[str] = mapped_column(String(14), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("provider_profiles.user_id"), index=True)
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_offerings.id"))
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quotations.id"))
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    blocked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    assignment_mode: Mapped[str] = mapped_column(String(12), default="auto")  # auto | chosen | admin
    address_snapshot: Mapped[dict] = mapped_column(JSONB)
    outward_code: Mapped[str] = mapped_column(String(5), index=True)
    inputs: Mapped[dict] = mapped_column(JSONB, default=dict)
    customer_notes: Mapped[str | None] = mapped_column(String(500))
    total_pence: Mapped[int] = mapped_column(Integer)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    terms_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_late: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[str | None] = mapped_column(String(12))  # customer | provider | admin | system
    cancel_reason: Mapped[str | None] = mapped_column(String(300))
    rescheduled_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_provider_ids: Mapped[list] = mapped_column(JSONB, default=list)
    lines: Mapped[list["BookingLine"]] = relationship(lazy="selectin", cascade="all, delete-orphan", order_by="BookingLine.position")
    history: Mapped[list["BookingStatusHistory"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="BookingStatusHistory.at"
    )


class BookingLine(Base):
    __tablename__ = "booking_lines"
    id: Mapped[uuid.UUID] = pk()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(200))
    amount_pence: Mapped[int] = mapped_column(Integer)


class BookingStatusHistory(Base):
    __tablename__ = "booking_status_history"
    id: Mapped[uuid.UUID] = pk()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(String(300))


class BookingMessage(Base):
    __tablename__ = "booking_messages"
    id: Mapped[uuid.UUID] = pk()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"
    id: Mapped[uuid.UUID] = pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_offerings.id"))
    address_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("addresses.id"))
    preferred_provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("provider_profiles.user_id"))
    frequency: Mapped[str] = mapped_column(String(12))  # weekly | fortnightly
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    addon_codes: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | paused | cancelled
    next_visit_on: Mapped[date] = mapped_column(Date)
    payment_method_ref: Mapped[str | None] = mapped_column(String(80))
    skipped_dates: Mapped[list] = mapped_column(JSONB, default=list)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FavouriteProvider(Base):
    __tablename__ = "favourite_providers"
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("provider_profiles.user_id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
