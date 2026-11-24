"""Verification rules. A provider is only bookable when every mandatory document for the
category is approved and unexpired. Badges shown to customers are derived from the same data."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogue import ServiceCategory, ServiceOffering
from app.models.providers import ProviderDocument, ProviderProfile

DOC_LABELS = {
    "identity": "Identity document checked",
    "right_to_work": "Right to work checked",
    "public_liability": "Public liability insurance certificate seen",
    "dbs": "Enhanced DBS certificate seen",
    "qualification": "Qualification seen",
}
DOC_TYPES = tuple(DOC_LABELS)


def valid_docs(db: Session, provider_id, today: date | None = None) -> dict[str, ProviderDocument]:
    today = today or date.today()
    docs = db.scalars(select(ProviderDocument).where(ProviderDocument.provider_id == provider_id, ProviderDocument.status == "approved"))
    best: dict[str, ProviderDocument] = {}
    for d in docs:
        if d.expires_on is not None and d.expires_on < today:
            continue
        cur = best.get(d.doc_type)
        if cur is None or (d.expires_on or date.max) > (cur.expires_on or date.max):
            best[d.doc_type] = d
    return best


def missing_requirements(db: Session, provider: ProviderProfile, category: ServiceCategory, today: date | None = None) -> list[str]:
    have = valid_docs(db, provider.user_id, today)
    return [r.document_type for r in category.requirements if r.is_mandatory and r.document_type not in have]


def provider_categories(db: Session, provider: ProviderProfile) -> list[ServiceCategory]:
    ids = [s.offering_id for s in provider.services]
    if not ids:
        return []
    offerings = db.scalars(select(ServiceOffering).where(ServiceOffering.id.in_(ids)))
    seen: dict = {}
    for o in offerings:
        seen[o.category_id] = o.category
    return list(seen.values())


def verification_gaps(db: Session, provider: ProviderProfile) -> dict[str, list[str]]:
    return {c.slug: missing_requirements(db, provider, c) for c in provider_categories(db, provider)}


def is_bookable_for(db: Session, provider: ProviderProfile, offering: ServiceOffering, today: date | None = None) -> bool:
    if provider.status != "approved" or not provider.accepts_jobs:
        return False
    if offering.id not in {s.offering_id for s in provider.services}:
        return False
    return not missing_requirements(db, provider, offering.category, today)


def badges(db: Session, provider_id) -> list[dict]:
    """Only claims backed by an approved, unexpired document are returned."""
    out = []
    for t, d in valid_docs(db, provider_id).items():
        if t == "qualification":
            continue
        out.append({"type": t, "label": DOC_LABELS[t], "valid_until": d.expires_on.isoformat() if d.expires_on else None})
    return sorted(out, key=lambda b: b["type"])
