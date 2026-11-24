import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin
from app.models.identity import pk


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating between 1 and 5"), CheckConstraint("punctuality between 1 and 5"))
    id: Mapped[uuid.UUID] = pk()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("provider_profiles.user_id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    punctuality: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(1500))
    provider_reply: Mapped[str | None] = mapped_column(String(1000))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)


class Complaint(Base, TimestampMixin):
    __tablename__ = "complaints"
    id: Mapped[uuid.UUID] = pk()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("provider_profiles.user_id"), index=True)
    category: Mapped[str] = mapped_column(String(30))  # quality | lateness | no_show | damage | conduct | safety | other
    severity: Mapped[str] = mapped_column(String(10), default="normal")  # normal | high
    description: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(14), default="open")  # open | investigating | resolved | rejected
    resolution: Mapped[str | None] = mapped_column(String(1000))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportTicket(Base, TimestampMixin):
    __tablename__ = "support_tickets"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    contact_email: Mapped[str | None] = mapped_column(String(200))
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"))
    kind: Mapped[str] = mapped_column(String(20), default="general")  # general | provider_dispute | payout | account
    subject: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(3000))
    status: Mapped[str] = mapped_column(String(12), default="open")  # open | in_progress | closed
    response: Mapped[str | None] = mapped_column(String(3000))
    handled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Promotion(Base, TimestampMixin):
    __tablename__ = "promotions"
    __table_args__ = (CheckConstraint("kind in ('percent','fixed')"),)
    id: Mapped[uuid.UUID] = pk()
    code: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(10))
    value: Mapped[int] = mapped_column(Integer)  # bps if percent, pence if fixed
    min_spend_pence: Mapped[int] = mapped_column(Integer, default=0)
    max_discount_pence: Mapped[int | None] = mapped_column(Integer)
    first_booking_only: Mapped[bool] = mapped_column(Boolean, default=False)
    max_redemptions: Mapped[int | None] = mapped_column(Integer)
    per_user_limit: Mapped[int] = mapped_column(Integer, default=1)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    channel: Mapped[str | None] = mapped_column(String(40))
    redemption_count: Mapped[int] = mapped_column(Integer, default=0)


class PromotionRedemption(Base):
    __tablename__ = "promotion_redemptions"
    id: Mapped[uuid.UUID] = pk()
    promotion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("promotions.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), unique=True)
    discount_pence: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    amount_pence: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(40))  # referral_reward | referral_welcome | booking_spend | booking_refund | admin
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(10))  # in_app | email | sms
    template: Mapped[str] = mapped_column(String(60))
    to_address: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="queued")  # queued | sent | failed
    error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
