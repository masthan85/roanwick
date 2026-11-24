"""Slot search and provider matching. Working hours are stored in Europe/London local time."""
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models.bookings import BLOCKING_STATUSES, Booking, FavouriteProvider
from app.models.catalogue import ServiceOffering
from app.models.providers import AvailabilityException, AvailabilityRule, ProviderArea, ProviderProfile, ProviderService
from app.services.config_store import get_setting
from app.services.verification import is_bookable_for

LONDON = ZoneInfo("Europe/London")
GRID_MINUTES = 30


def local(dt: datetime) -> datetime:
    return dt.astimezone(LONDON)


def to_utc(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=LONDON).astimezone(ZoneInfo("UTC"))


def eligible_providers(db: Session, offering: ServiceOffering, outward: str, today: date | None = None) -> list[ProviderProfile]:
    stmt = (
        select(ProviderProfile)
        .join(ProviderService, ProviderService.provider_id == ProviderProfile.user_id)
        .join(ProviderArea, ProviderArea.provider_id == ProviderProfile.user_id)
        .where(
            ProviderService.offering_id == offering.id,
            ProviderArea.outward_code == outward,
            ProviderProfile.status == "approved",
            ProviderProfile.accepts_jobs.is_(True),
        )
    )
    return [p for p in db.scalars(stmt).unique() if is_bookable_for(db, p, offering, today)]


def _windows_for(rules, exceptions, d: date) -> list[tuple[time, time]]:
    day_ex = [e for e in exceptions if e.on_date == d]
    if any((not e.is_available) and e.start_time is None for e in day_ex):
        return []
    windows = [(r.start_time, r.end_time) for r in rules if r.weekday == d.weekday()]
    windows += [(e.start_time, e.end_time) for e in day_ex if e.is_available and e.start_time and e.end_time]
    blocked = [(e.start_time, e.end_time) for e in day_ex if not e.is_available and e.start_time and e.end_time]
    if not blocked:
        return windows
    out = []
    for s, e in windows:
        cur = s
        for bs, be in sorted(blocked):
            if be <= cur or bs >= e:
                continue
            if bs > cur:
                out.append((cur, bs))
            cur = max(cur, be)
        if cur < e:
            out.append((cur, e))
    return out


def provider_free(
    db: Session, provider_id: uuid.UUID, start: datetime, end: datetime, buffer_minutes: int,
    *, rules=None, exceptions=None, bookings=None, ignore_booking_id: uuid.UUID | None = None,
) -> bool:
    """True when the interval sits inside working hours and does not collide with another booking."""
    if rules is None:
        rules = db.scalars(select(AvailabilityRule).where(AvailabilityRule.provider_id == provider_id)).all()
    if exceptions is None:
        exceptions = db.scalars(select(AvailabilityException).where(AvailabilityException.provider_id == provider_id)).all()
    ls, le = local(start), local(end)
    if ls.date() != le.date():
        return False
    if not any(ws <= ls.time() and le.time() <= we for ws, we in _windows_for(rules, exceptions, ls.date())):
        return False
    block_end = end + timedelta(minutes=buffer_minutes)
    if bookings is None:
        bookings = db.scalars(
            select(Booking).where(
                Booking.provider_id == provider_id,
                Booking.status.in_(BLOCKING_STATUSES),
                Booking.starts_at < block_end,
                Booking.blocked_until > start,
            )
        ).all()
    for b in bookings:
        if b.id == ignore_booking_id:
            continue
        if b.starts_at < block_end and b.blocked_until > start:
            return False
    return True


def search_slots(
    db: Session, offering: ServiceOffering, outward: str, duration_minutes: int, from_date: date, days: int,
    provider_id: uuid.UUID | None = None,
) -> dict[str, list[dict]]:
    now = utcnow()
    earliest = now + timedelta(hours=int(get_setting(db, "min_notice_hours")))
    horizon = now.date() + timedelta(days=int(get_setting(db, "booking_horizon_days")))
    providers = eligible_providers(db, offering, outward)
    if provider_id:
        providers = [p for p in providers if p.user_id == provider_id]
    if not providers:
        return {}
    ids = [p.user_id for p in providers]
    rules = db.scalars(select(AvailabilityRule).where(AvailabilityRule.provider_id.in_(ids))).all()
    excs = db.scalars(select(AvailabilityException).where(AvailabilityException.provider_id.in_(ids))).all()
    first = to_utc(from_date, time(0, 0))
    last = to_utc(from_date + timedelta(days=days + 1), time(0, 0))
    booked = db.scalars(
        select(Booking).where(
            Booking.provider_id.in_(ids), Booking.status.in_(BLOCKING_STATUSES), Booking.starts_at < last, Booking.blocked_until > first
        )
    ).all()
    by_p = lambda coll, pid: [x for x in coll if x.provider_id == pid]  # noqa: E731
    result: dict[str, list[dict]] = {}
    for i in range(days):
        d = from_date + timedelta(days=i)
        if d > horizon:
            break
        slots = []
        for h in range(6 * 60, 22 * 60, GRID_MINUTES):
            t = time(h // 60, h % 60)
            start = to_utc(d, t)
            if start < earliest:
                continue
            end = start + timedelta(minutes=duration_minutes)
            n = sum(
                1
                for p in providers
                if provider_free(db, p.user_id, start, end, offering.buffer_minutes,
                                 rules=by_p(rules, p.user_id), exceptions=by_p(excs, p.user_id), bookings=by_p(booked, p.user_id))
            )
            if n:
                slots.append({"time": t.strftime("%H:%M"), "starts_at": start.isoformat(), "professionals": n})
        if slots:
            result[d.isoformat()] = slots
    return result


def rank_candidates(
    db: Session, offering: ServiceOffering, outward: str, start: datetime, duration_minutes: int,
    *, prefer: list[uuid.UUID] | None = None, exclude: list[uuid.UUID] | None = None, customer_id: uuid.UUID | None = None,
) -> list[ProviderProfile]:
    end = start + timedelta(minutes=duration_minutes)
    favs = set()
    if customer_id:
        favs = set(db.scalars(select(FavouriteProvider.provider_id).where(FavouriteProvider.customer_id == customer_id)))
    prefer = prefer or []
    out = []
    for p in eligible_providers(db, offering, outward):
        if exclude and p.user_id in exclude:
            continue
        if provider_free(db, p.user_id, start, end, offering.buffer_minutes):
            out.append(p)

    def key(p: ProviderProfile):
        # Preferred first, then favourites, then quality (rating, fewer late arrivals), then less-experienced to spread work.
        return (
            0 if p.user_id in prefer else 1,
            0 if p.user_id in favs else 1,
            -(float(p.rating_avg) if p.rating_count >= 3 else 4.0),
            p.late_count + 2 * p.cancel_count,
            p.jobs_completed,
        )

    return sorted(out, key=key)
