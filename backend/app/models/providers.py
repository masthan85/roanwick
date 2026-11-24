import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.models.identity import pk


class ProviderProfile(Base, TimestampMixin):
    __tablename__ = "provider_profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80))
    bio: Mapped[str] = mapped_column(Text, default="")
    years_experience: Mapped[int | None] = mapped_column(Integer)
    languages: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    # draft | submitted | approved | rejected | suspended
    status_reason: Mapped[str | None] = mapped_column(String(300))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    commission_override_bps: Mapped[int | None] = mapped_column(Integer)
    stripe_account_id: Mapped[str | None] = mapped_column(String(80))
    payouts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    accepts_jobs: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_accept: Mapped[bool] = mapped_column(Boolean, default=True)
    rating_avg: Mapped[float] = mapped_column(Numeric(3, 2), default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    jobs_completed: Mapped[int] = mapped_column(Integer, default=0)
    late_count: Mapped[int] = mapped_column(Integer, default=0)
    cancel_count: Mapped[int] = mapped_column(Integer, default=0)
    services: Mapped[list["ProviderService"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    areas: Mapped[list["ProviderArea"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class ProviderService(Base):
    __tablename__ = "provider_services"
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("provider_profiles.user_id", ondelete="CASCADE"), primary_key=True)
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_offerings.id"), primary_key=True)


class ProviderArea(Base):
    __tablename__ = "provider_areas"
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("provider_profiles.user_id", ondelete="CASCADE"), primary_key=True)
    outward_code: Mapped[str] = mapped_column(ForeignKey("service_areas.outward_code"), primary_key=True)


class AvailabilityRule(Base):
    """Weekly working hours, expressed in Europe/London local time. weekday: 0 = Monday."""

    __tablename__ = "availability_rules"
    id: Mapped[uuid.UUID] = pk()
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("provider_profiles.user_id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class AvailabilityException(Base):
    """Date-specific override. is_available=False with no times blocks the whole day."""

    __tablename__ = "availability_exceptions"
    id: Mapped[uuid.UUID] = pk()
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("provider_profiles.user_id", ondelete="CASCADE"), index=True)
    on_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    is_available: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(200))


class ProviderDocument(Base, TimestampMixin):
    __tablename__ = "provider_documents"
    id: Mapped[uuid.UUID] = pk()
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("provider_profiles.user_id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(40))  # identity | right_to_work | public_liability | dbs | qualification
    title: Mapped[str] = mapped_column(String(120))
    storage_key: Mapped[str] = mapped_column(String(200))
    original_name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str | None] = mapped_column(String(80))
    issued_on: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending | approved | rejected
    review_notes: Mapped[str | None] = mapped_column(String(300))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_sent_for: Mapped[date | None] = mapped_column(Date)
