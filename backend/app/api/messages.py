import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.db import utcnow
from app.core.deps import DB, CurrentUser, user_permissions
from app.core.errors import Conflict, Forbidden, NotFound
from app.models.bookings import Booking, BookingMessage
from app.models.identity import User
from app.services.notify import notify

router = APIRouter(tags=["Messaging"])


def _access(db, user: User, b: Booking) -> str:
    if user.id == b.customer_id:
        return "customer"
    if user.id == b.provider_id:
        return "provider"
    if "bookings.read" in user_permissions(db, user):
        return "staff"
    raise NotFound("Booking not found.")


@router.get("/bookings/{booking_id}/messages", summary="Messages between customer and professional")
def list_messages(booking_id: uuid.UUID, user: CurrentUser, db: DB):
    b = db.get(Booking, booking_id)
    if b is None:
        raise NotFound("Booking not found.")
    role = _access(db, user, b)
    rows = db.scalars(select(BookingMessage).where(BookingMessage.booking_id == b.id).order_by(BookingMessage.created_at)).all()
    for m in rows:
        if m.sender_id != user.id and m.read_at is None and role != "staff":
            m.read_at = utcnow()
    return [{"id": str(m.id), "mine": m.sender_id == user.id, "sender_role": "customer" if m.sender_id == b.customer_id else "professional",
             "body": m.body, "created_at": m.created_at} for m in rows]


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.post("/bookings/{booking_id}/messages", status_code=201)
def send_message(booking_id: uuid.UUID, body: MessageIn, user: CurrentUser, db: DB):
    b = db.get(Booking, booking_id)
    if b is None:
        raise NotFound("Booking not found.")
    role = _access(db, user, b)
    if role == "staff":
        raise Forbidden("Staff can read but not post in booking conversations.")
    if b.status in ("pending_payment", "expired"):
        raise Conflict("Messaging opens once the booking is paid.", code="messaging_closed")
    m = BookingMessage(booking_id=b.id, sender_id=user.id, body=body.body.strip())
    db.add(m)
    other = b.provider_id if role == "customer" else b.customer_id
    if other:
        notify(db, db.get(User, other), "new_message", f"New message about {b.reference}", body.body[:140], ("in_app",))
    db.flush()
    return {"id": str(m.id)}
