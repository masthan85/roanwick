import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.core.deps import DB, Pagination, audit, paginate, require_permission
from app.core.errors import Conflict, NotFound, Unprocessable
from app.models.catalogue import (
    Bundle, CategoryRequirement, OfferingAddon, PriceTier, ServiceArea, ServiceCategory, ServiceOffering,
)
from app.models.engagement import Promotion
from app.models.finance import BusinessCost
from app.models.identity import AuditEvent, User
from app.models.system import AppSetting, FeatureFlag
from app.services import reports
from app.services.config_store import DEFAULT_SETTINGS
from app.services.verification import DOC_TYPES

router = APIRouter(prefix="/admin", tags=["Administration"])


def perm(*keys: str):
    return Depends(require_permission(*keys))


# ---------- catalogue ----------
def _cat(c: ServiceCategory) -> dict:
    return {"slug": c.slug, "name": c.name, "summary": c.summary, "is_active": c.is_active, "requires_compliance_review": c.requires_compliance_review,
            "requirements": [{"document_type": r.document_type, "is_mandatory": r.is_mandatory} for r in c.requirements],
            "offerings": [{"id": str(o.id), "slug": o.slug, "name": o.name, "pricing_model": o.pricing_model, "hourly_rate_pence": o.hourly_rate_pence, "is_active": o.is_active,
                           "min_minutes": o.min_minutes, "max_minutes": o.max_minutes, "buffer_minutes": o.buffer_minutes, "supports_recurring": o.supports_recurring,
                           "addons": [{"code": a.code, "name": a.name, "price_pence": a.price_pence, "extra_minutes": a.extra_minutes, "is_active": a.is_active} for a in o.addons],
                           "tiers": [{"bedrooms": t.bedrooms, "label": t.label, "price_pence": t.price_pence, "duration_minutes": t.duration_minutes} for t in sorted(o.tiers, key=lambda t: t.bedrooms)]}
                          for o in c.offerings]}


@router.get("/catalogue")
def catalogue(db: DB, actor: User = perm("catalogue.manage")):
    return [_cat(c) for c in db.scalars(select(ServiceCategory).order_by(ServiceCategory.sort_order)).unique()]


class CategoryPatch(BaseModel):
    is_active: bool | None = None
    confirm_compliance_reviewed: bool = False
    name: str | None = Field(default=None, max_length=80)
    summary: str | None = Field(default=None, max_length=300)


@router.patch("/categories/{slug}")
def patch_category(slug: str, body: CategoryPatch, request: Request, db: DB, actor: User = perm("catalogue.manage")):
    c = db.scalar(select(ServiceCategory).where(ServiceCategory.slug == slug))
    if c is None:
        raise NotFound("Category not found.")
    before = {"is_active": c.is_active}
    if body.is_active:
        if c.requires_compliance_review:
            if not any(r.is_mandatory for r in c.requirements):
                raise Unprocessable(
                    "This category needs its verification requirements defined (and reviewed by someone qualified) before it can be switched on.",
                    code="compliance_review_required",
                )
            if not body.confirm_compliance_reviewed:
                raise Unprocessable("Confirm that the compliance requirements for this category have been reviewed.", code="compliance_review_required")
    for k in ("is_active", "name", "summary"):
        v = getattr(body, k)
        if v is not None:
            setattr(c, k, v)
    audit(db, request, actor, "category.updated", "category", c.slug, before, body.model_dump(exclude_none=True))
    return _cat(c)


class RequirementsIn(BaseModel):
    requirements: list[dict]


@router.put("/categories/{slug}/requirements", summary="Define the documents a professional needs for this category")
def set_requirements(slug: str, body: RequirementsIn, request: Request, db: DB, actor: User = perm("catalogue.manage")):
    c = db.scalar(select(ServiceCategory).where(ServiceCategory.slug == slug))
    if c is None:
        raise NotFound("Category not found.")
    before = [{"document_type": r.document_type, "is_mandatory": r.is_mandatory} for r in c.requirements]
    new = []
    for r in body.requirements:
        if r.get("document_type") not in DOC_TYPES:
            raise Unprocessable(f"Unknown document type. Use one of: {', '.join(DOC_TYPES)}.")
        new.append(CategoryRequirement(document_type=r["document_type"], is_mandatory=bool(r.get("is_mandatory", True))))
    c.requirements = new
    audit(db, request, actor, "category.requirements_changed", "category", c.slug, before, body.requirements)
    return _cat(c)


class AddonIn(BaseModel):
    code: str = Field(pattern="^[a-z0-9_]{2,40}$")
    name: str = Field(max_length=80)
    price_pence: int = Field(ge=0, le=100000)
    extra_minutes: int = Field(default=0, ge=0, le=240)
    is_active: bool = True


class TierIn(BaseModel):
    bedrooms: int = Field(ge=0, le=10)
    label: str
    price_pence: int = Field(ge=0, le=500000)
    duration_minutes: int = Field(ge=30, le=1440)


class OfferingPatch(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=300)
    hourly_rate_pence: int | None = Field(default=None, ge=500, le=20000)
    min_minutes: int | None = Field(default=None, ge=30, le=1440)
    max_minutes: int | None = Field(default=None, ge=30, le=1440)
    buffer_minutes: int | None = Field(default=None, ge=0, le=120)
    is_active: bool | None = None
    addons: list[AddonIn] | None = None
    tiers: list[TierIn] | None = None


@router.patch("/offerings/{oid}", summary="Change prices, durations, add-ons or tiers")
def patch_offering(oid: uuid.UUID, body: OfferingPatch, request: Request, db: DB, actor: User = perm("catalogue.manage")):
    o = db.get(ServiceOffering, oid)
    if o is None:
        raise NotFound("Service not found.")
    before = {"hourly_rate_pence": o.hourly_rate_pence, "min_minutes": o.min_minutes, "is_active": o.is_active,
              "addons": [(a.code, a.price_pence) for a in o.addons], "tiers": [(t.bedrooms, t.price_pence) for t in o.tiers]}
    data = body.model_dump(exclude_unset=True, exclude={"addons", "tiers"})
    for k, v in data.items():
        setattr(o, k, v)
    if o.max_minutes < o.min_minutes:
        raise Unprocessable("Maximum duration cannot be below the minimum.")
    if body.addons is not None:
        o.addons = [OfferingAddon(**a.model_dump()) for a in body.addons]
    if body.tiers is not None:
        o.tiers = [PriceTier(**t.model_dump()) for t in body.tiers]
    audit(db, request, actor, "offering.updated", "offering", o.id, before, body.model_dump(exclude_unset=True, mode="json"))
    return _cat(o.category)


class OfferingCreate(BaseModel):
    category_slug: str
    slug: str = Field(pattern="^[a-z0-9-]{3,60}$")
    name: str = Field(min_length=3, max_length=100)
    summary: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=3000)
    pricing_model: str = Field(pattern="^(hourly|tiered)$")
    hourly_rate_pence: int | None = Field(default=None, ge=500, le=20000)
    min_minutes: int = Field(default=120, ge=30, le=1440)
    max_minutes: int = Field(default=480, ge=30, le=1440)
    step_minutes: int = Field(default=30, ge=15, le=120)
    buffer_minutes: int = Field(default=30, ge=0, le=120)
    supports_recurring: bool = False
    included: list[str] = []
    excluded: list[str] = []
    tiers: list[TierIn] = []

    @model_validator(mode="after")
    def _chk(self):
        if self.pricing_model == "hourly" and not self.hourly_rate_pence:
            raise ValueError("Hourly services need an hourly rate.")
        if self.pricing_model == "tiered" and not self.tiers:
            raise ValueError("Fixed-price services need at least one size and price.")
        if self.max_minutes < self.min_minutes:
            raise ValueError("Maximum duration cannot be below the minimum.")
        return self


@router.post("/offerings", status_code=201, summary="Create a new service within a category")
def create_offering(body: OfferingCreate, request: Request, db: DB, actor: User = perm("catalogue.manage")):
    cat = db.scalar(select(ServiceCategory).where(ServiceCategory.slug == body.category_slug))
    if cat is None:
        raise NotFound("Category not found.")
    if db.scalar(select(ServiceOffering.id).where(ServiceOffering.slug == body.slug)):
        raise Conflict("A service with that address already exists.", code="duplicate_slug")
    o = ServiceOffering(category_id=cat.id, **body.model_dump(exclude={"category_slug", "tiers"}))
    o.tiers = [PriceTier(**t.model_dump()) for t in body.tiers]
    db.add(o)
    db.flush()
    audit(db, request, actor, "offering.created", "offering", o.id, None, body.model_dump(mode="json"))
    return _cat(cat)


# ---------- bundles ----------
class BundleIn(BaseModel):
    slug: str = Field(pattern="^[a-z0-9-]{3,60}$")
    name: str = Field(min_length=3, max_length=100)
    description: str = Field(default="", max_length=400)
    offering_id: uuid.UUID
    addon_codes: list[str] = Field(min_length=1)
    discount_bps: int = Field(ge=0, le=5000)
    is_active: bool = True


def _bundle(db, b: Bundle) -> dict:
    o = db.get(ServiceOffering, b.offering_id)
    return {"id": str(b.id), "slug": b.slug, "name": b.name, "description": b.description, "offering_id": str(b.offering_id), "offering": o.name,
            "addon_codes": b.addon_codes, "discount_bps": b.discount_bps, "is_active": b.is_active}


def _check_bundle(db, body: BundleIn) -> None:
    o = db.get(ServiceOffering, body.offering_id)
    if o is None:
        raise NotFound("Service not found.")
    valid = {a.code for a in o.addons if a.is_active}
    if set(body.addon_codes) - valid:
        raise Unprocessable(f"Unknown extras for this service: {', '.join(sorted(set(body.addon_codes) - valid))}.")


@router.get("/bundles")
def list_bundles(db: DB, actor: User = perm("catalogue.manage")):
    return [_bundle(db, b) for b in db.scalars(select(Bundle).order_by(Bundle.name))]


@router.post("/bundles", status_code=201)
def create_bundle(body: BundleIn, request: Request, db: DB, actor: User = perm("catalogue.manage")):
    if db.scalar(select(Bundle.id).where(Bundle.slug == body.slug)):
        raise Conflict("A bundle with that address already exists.", code="duplicate_slug")
    _check_bundle(db, body)
    b = Bundle(**body.model_dump())
    db.add(b)
    db.flush()
    audit(db, request, actor, "bundle.created", "bundle", b.id, None, body.model_dump(mode="json"))
    return _bundle(db, b)


@router.put("/bundles/{bid}")
def update_bundle(bid: uuid.UUID, body: BundleIn, request: Request, db: DB, actor: User = perm("catalogue.manage")):
    b = db.get(Bundle, bid)
    if b is None:
        raise NotFound("Bundle not found.")
    _check_bundle(db, body)
    before = _bundle(db, b)
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    audit(db, request, actor, "bundle.updated", "bundle", b.id, before, body.model_dump(mode="json"))
    return _bundle(db, b)


# ---------- coverage ----------
@router.get("/areas")
def areas(db: DB, actor: User = perm("coverage.manage")):
    return [{"outward_code": a.outward_code, "name": a.name, "is_active": a.is_active} for a in db.scalars(select(ServiceArea).order_by(ServiceArea.outward_code))]


class AreaIn(BaseModel):
    outward_code: str = Field(pattern="^[A-Za-z]{1,2}[0-9][A-Za-z0-9]?$")
    name: str = Field(max_length=80)
    is_active: bool = True


@router.put("/areas")
def upsert_area(body: AreaIn, request: Request, db: DB, actor: User = perm("coverage.manage")):
    code = body.outward_code.upper()
    a = db.get(ServiceArea, code)
    before = None if a is None else {"is_active": a.is_active, "name": a.name}
    if a is None:
        a = ServiceArea(outward_code=code, name=body.name, is_active=body.is_active)
        db.add(a)
    else:
        a.name, a.is_active = body.name, body.is_active
    audit(db, request, actor, "area.upserted", "area", code, before, {"is_active": a.is_active, "name": a.name})
    return {"outward_code": code, "name": a.name, "is_active": a.is_active}


# ---------- promotions ----------
class PromoIn(BaseModel):
    code: str = Field(pattern="^[A-Za-z0-9_-]{3,30}$")
    description: str = Field(default="", max_length=200)
    kind: str = Field(pattern="^(percent|fixed)$")
    value: int = Field(gt=0)
    min_spend_pence: int = Field(default=0, ge=0)
    max_discount_pence: int | None = Field(default=None, ge=1)
    first_booking_only: bool = False
    max_redemptions: int | None = Field(default=None, ge=1)
    per_user_limit: int = Field(default=1, ge=1)
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool = True
    channel: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def _chk(self):
        if self.kind == "percent" and self.value > 5000:
            raise ValueError("Percentage discounts above 50% need to be entered in pence-based form deliberately; maximum is 5000 basis points.")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Valid-to date must not be before valid-from.")
        return self


def _promo(p: Promotion) -> dict:
    return {c.name: getattr(p, c.name) for c in Promotion.__table__.columns if c.name not in ("created_at", "updated_at")} | {"id": str(p.id)}


@router.get("/promotions")
def promotions(db: DB, actor: User = perm("promotions.manage")):
    return [_promo(p) for p in db.scalars(select(Promotion).order_by(Promotion.created_at.desc()))]


@router.post("/promotions", status_code=201)
def create_promo(body: PromoIn, request: Request, db: DB, actor: User = perm("promotions.manage")):
    code = body.code.upper()
    if db.scalar(select(Promotion.id).where(Promotion.code == code)):
        raise Conflict("That code already exists.", code="duplicate_code")
    p = Promotion(**{**body.model_dump(), "code": code})
    db.add(p)
    db.flush()
    audit(db, request, actor, "promotion.created", "promotion", p.id, None, body.model_dump(mode="json"))
    return _promo(p)


@router.put("/promotions/{pid}")
def update_promo(pid: uuid.UUID, body: PromoIn, request: Request, db: DB, actor: User = perm("promotions.manage")):
    p = db.get(Promotion, pid)
    if p is None:
        raise NotFound("Promotion not found.")
    before = _promo(p)
    for k, v in body.model_dump().items():
        setattr(p, k, v.upper() if k == "code" else v)
    audit(db, request, actor, "promotion.updated", "promotion", p.id, before, body.model_dump(mode="json"))
    return _promo(p)


# ---------- settings and flags ----------
@router.get("/settings")
def settings_list(db: DB, actor: User = perm("settings.manage")):
    stored = {s.key: s for s in db.scalars(select(AppSetting))}
    return [{"key": k, "value": stored[k].value if k in stored else default, "description": desc} for k, (default, desc) in DEFAULT_SETTINGS.items()]


class SettingIn(BaseModel):
    value: int | bool | list | float | str


def _validate_setting(key: str, value):
    default = DEFAULT_SETTINGS[key][0]
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise Unprocessable("This setting must be true or false.")
    elif isinstance(default, int):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise Unprocessable("This setting must be a whole number of zero or more.")
        if key in ("commission_bps", "processing_fee_bps") and value > 5000:
            raise Unprocessable("That rate is above the 50% safety limit.")
    elif key == "cancellation_tiers":
        if not isinstance(value, list) or not value:
            raise Unprocessable("Provide a list of tiers.")
        for t in value:
            if not isinstance(t, dict) or not {"hours_before", "refund_bps"} <= set(t) or not (0 <= t["refund_bps"] <= 10000) or t["hours_before"] < 0:
                raise Unprocessable("Each tier needs hours_before (0 or more) and refund_bps (0 to 10000).")
        if 0 not in [t["hours_before"] for t in value]:
            raise Unprocessable("Include a final tier with hours_before 0.")


@router.put("/settings/{key}")
def update_setting(key: str, body: SettingIn, request: Request, db: DB, actor: User = perm("settings.manage")):
    if key not in DEFAULT_SETTINGS:
        raise NotFound("Unknown setting.")
    _validate_setting(key, body.value)
    row = db.get(AppSetting, key)
    before = row.value if row else DEFAULT_SETTINGS[key][0]
    if row is None:
        row = AppSetting(key=key, value=body.value, description=DEFAULT_SETTINGS[key][1])
        db.add(row)
    else:
        row.value = body.value
    audit(db, request, actor, "setting.changed", "setting", key, {"value": before}, {"value": body.value})
    return {"key": key, "value": body.value}


@router.get("/flags")
def flags(db: DB, actor: User = perm("settings.manage")):
    return [{"key": f.key, "enabled": f.enabled, "description": f.description} for f in db.scalars(select(FeatureFlag).order_by(FeatureFlag.key))]


class FlagIn(BaseModel):
    enabled: bool


@router.put("/flags/{key}")
def set_flag(key: str, body: FlagIn, request: Request, db: DB, actor: User = perm("settings.manage")):
    f = db.get(FeatureFlag, key)
    if f is None:
        raise NotFound("Unknown flag.")
    if key == "maintenance_bundles" and body.enabled:
        raise Unprocessable("Maintenance bundles involve regulated trades. Define their compliance requirements first.", code="compliance_review_required")
    before = f.enabled
    f.enabled = body.enabled
    audit(db, request, actor, "flag.changed", "flag", key, {"enabled": before}, {"enabled": body.enabled})
    return {"key": key, "enabled": f.enabled}


# ---------- audit and manual costs ----------
@router.get("/audit")
def audit_log(db: DB, p: Pagination, actor: User = perm("audit.read"), action: str | None = None, entity_type: str | None = None, actor_id: uuid.UUID | None = None):
    stmt = select(AuditEvent).order_by(AuditEvent.at.desc())
    if action:
        stmt = stmt.where(AuditEvent.action.ilike(f"{action}%"))
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_user_id == actor_id)

    def conv(e: AuditEvent):
        u = db.get(User, e.actor_user_id) if e.actor_user_id else None
        return {"id": str(e.id), "at": e.at, "actor": u.email if u else None, "actor_role": e.actor_role, "action": e.action, "entity_type": e.entity_type,
                "entity_id": e.entity_id, "before": e.before, "after": e.after, "ip": e.ip}

    return paginate(db, stmt, p, conv)


class CostIn(BaseModel):
    category: str = Field(pattern="^(marketing|support|insurance|tools|other)$")
    channel: str | None = Field(default=None, max_length=40)
    period_start: date
    period_end: date
    amount_pence: int = Field(gt=0, le=100_000_000)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _o(self):
        if self.period_end < self.period_start:
            raise ValueError("Period end must not be before the start.")
        return self


@router.get("/costs")
def costs(db: DB, actor: User = perm("finance.read")):
    return [{"id": str(c.id), "category": c.category, "channel": c.channel, "period_start": c.period_start, "period_end": c.period_end,
             "amount_pence": c.amount_pence, "note": c.note, "basis": "manual"} for c in db.scalars(select(BusinessCost).order_by(BusinessCost.period_start.desc()))]


@router.post("/costs", status_code=201)
def add_cost(body: CostIn, request: Request, db: DB, actor: User = perm("finance.manage")):
    c = BusinessCost(**body.model_dump(), entered_by=actor.id)
    db.add(c)
    db.flush()
    audit(db, request, actor, "cost.added", "business_cost", c.id, None, body.model_dump(mode="json"))
    return {"id": str(c.id)}


@router.delete("/costs/{cid}", status_code=204)
def delete_cost(cid: uuid.UUID, request: Request, db: DB, actor: User = perm("finance.manage")):
    c = db.get(BusinessCost, cid)
    if c is None:
        raise NotFound("Cost not found.")
    audit(db, request, actor, "cost.deleted", "business_cost", c.id, {"amount_pence": c.amount_pence, "category": c.category}, None)
    db.delete(c)


# ---------- reports ----------
def _range(from_: date | None, to: date | None) -> tuple[date, date]:
    end = to or date.today()
    start = from_ or end - timedelta(days=29)
    if start > end or (end - start).days > 800:
        raise Unprocessable("Choose a valid date range of up to 800 days.")
    return start, end


@router.get("/reports/finance", summary="Revenue, costs and contribution margin")
def report_finance(db: DB, actor: User = perm("finance.read"), from_: date | None = Query(default=None, alias="from"), to: date | None = None):
    return reports.finance_report(db, *_range(from_, to))


@router.get("/reports/operations")
def report_ops(db: DB, actor: User = perm("bookings.read"), from_: date | None = Query(default=None, alias="from"), to: date | None = None):
    return reports.operations_report(db, *_range(from_, to))


@router.get("/reports/growth", summary="Acquisition, funnel and retention")
def report_growth(db: DB, actor: User = perm("finance.read"), from_: date | None = Query(default=None, alias="from"), to: date | None = None):
    return reports.growth_report(db, *_range(from_, to))


# ---------- scheduled jobs (also runnable from the CLI: python -m app.jobs) ----------
@router.post("/jobs/run", summary="Run the scheduled maintenance jobs now")
def run_jobs(request: Request, db: DB, actor: User = perm("settings.manage")):
    from app.jobs import run_all

    result = run_all(db)
    audit(db, request, actor, "jobs.run_manually", "jobs", None, None, result)
    return result
