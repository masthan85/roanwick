import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.models.identity import pk


class ServiceCategory(Base, TimestampMixin):
    __tablename__ = "service_categories"
    id: Mapped[uuid.UUID] = pk()
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_compliance_review: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    offerings: Mapped[list["ServiceOffering"]] = relationship(back_populates="category", lazy="selectin")
    requirements: Mapped[list["CategoryRequirement"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class CategoryRequirement(Base):
    """Documents a provider must hold (approved and unexpired) before serving a category."""

    __tablename__ = "category_requirements"
    __table_args__ = (UniqueConstraint("category_id", "document_type"),)
    id: Mapped[uuid.UUID] = pk()
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_categories.id", ondelete="CASCADE"))
    document_type: Mapped[str] = mapped_column(String(40))
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)


class ServiceOffering(Base, TimestampMixin):
    __tablename__ = "service_offerings"
    __table_args__ = (CheckConstraint("pricing_model in ('hourly','tiered')"),)
    id: Mapped[uuid.UUID] = pk()
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_categories.id"))
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    included: Mapped[list] = mapped_column(JSONB, default=list)
    excluded: Mapped[list] = mapped_column(JSONB, default=list)
    pricing_model: Mapped[str] = mapped_column(String(10), default="hourly")
    hourly_rate_pence: Mapped[int | None] = mapped_column(Integer)
    min_minutes: Mapped[int] = mapped_column(Integer, default=120)
    max_minutes: Mapped[int] = mapped_column(Integer, default=480)
    step_minutes: Mapped[int] = mapped_column(Integer, default=30)
    buffer_minutes: Mapped[int] = mapped_column(Integer, default=30)
    supports_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[ServiceCategory] = relationship(back_populates="offerings", lazy="joined")
    addons: Mapped[list["OfferingAddon"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    tiers: Mapped[list["PriceTier"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    frequency_discounts: Mapped[list["FrequencyDiscount"]] = relationship(lazy="selectin", viewonly=True)


class OfferingAddon(Base):
    __tablename__ = "offering_addons"
    __table_args__ = (UniqueConstraint("offering_id", "code"),)
    id: Mapped[uuid.UUID] = pk()
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_offerings.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(80))
    price_pence: Mapped[int] = mapped_column(Integer)
    extra_minutes: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PriceTier(Base):
    __tablename__ = "price_tiers"
    __table_args__ = (UniqueConstraint("offering_id", "bedrooms"),)
    id: Mapped[uuid.UUID] = pk()
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_offerings.id", ondelete="CASCADE"))
    bedrooms: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(60))
    price_pence: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer)


class FrequencyDiscount(Base):
    __tablename__ = "frequency_discounts"
    __table_args__ = (UniqueConstraint("offering_id", "frequency"),)
    id: Mapped[uuid.UUID] = pk()
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_offerings.id", ondelete="CASCADE"))
    frequency: Mapped[str] = mapped_column(String(12))  # weekly | fortnightly
    percent_bps: Mapped[int] = mapped_column(Integer)  # 1000 = 10%


class ServiceArea(Base, TimestampMixin):
    __tablename__ = "service_areas"
    outward_code: Mapped[str] = mapped_column(String(5), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[float | None] = mapped_column(Numeric(9, 6))


class Quotation(Base, TimestampMixin):
    __tablename__ = "quotations"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_offerings.id"))
    postcode: Mapped[str] = mapped_column(String(10))
    outward_code: Mapped[str] = mapped_column(String(5))
    inputs: Mapped[dict] = mapped_column(JSONB)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    subtotal_pence: Mapped[int] = mapped_column(Integer)
    discount_pence: Mapped[int] = mapped_column(Integer, default=0)
    fee_pence: Mapped[int] = mapped_column(Integer, default=0)
    total_pence: Mapped[int] = mapped_column(Integer)
    promo_code: Mapped[str | None] = mapped_column(String(30))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    terms: Mapped[dict] = mapped_column(JSONB)  # cancellation terms snapshot
    lines: Mapped[list["QuotationLine"]] = relationship(lazy="selectin", cascade="all, delete-orphan", order_by="QuotationLine.position")


class QuotationLine(Base):
    __tablename__ = "quotation_lines"
    id: Mapped[uuid.UUID] = pk()
    quotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotations.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # labour | addon | discount | promo | fee | credit
    description: Mapped[str] = mapped_column(String(200))
    amount_pence: Mapped[int] = mapped_column(Integer)


class Bundle(Base, TimestampMixin):
    """A priced package of extras on one service, for example a move-out pack. The discount is funded by the platform."""

    __tablename__ = "bundles"
    id: Mapped[uuid.UUID] = pk()
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(400), default="")
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_offerings.id"))
    addon_codes: Mapped[list] = mapped_column(JSONB, default=list)
    discount_bps: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
