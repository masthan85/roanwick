import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import Conflict
from app.core.security import hash_password
from app.models.identity import CustomerProfile, Role, User

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def get_role(db: Session, key: str) -> Role:
    return db.scalar(select(Role).where(Role.key == key))


def create_user(db: Session, *, email: str, password: str | None, full_name: str, phone: str | None, role: str, marketing: bool = False) -> User:
    email = email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise Conflict("An account with this email already exists. Try signing in.", code="email_taken")
    u = User(
        email=email, password_hash=hash_password(password) if password else None, full_name=full_name.strip(), phone=phone,
        marketing_consent=marketing, terms_accepted_at=utcnow(),
    )
    u.roles = [get_role(db, role)]
    db.add(u)
    db.flush()
    return u


def new_referral_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(7))
        if not db.scalar(select(CustomerProfile.user_id).where(CustomerProfile.referral_code == code)):
            return code


def create_customer(db: Session, *, referral_code: str | None, source: str, **kw) -> User:
    u = create_user(db, role="customer", **kw)
    referrer = None
    if referral_code:
        referrer = db.scalar(select(CustomerProfile).where(CustomerProfile.referral_code == referral_code.strip().upper()))
    db.add(CustomerProfile(
        user_id=u.id, referral_code=new_referral_code(db), referred_by_user_id=referrer.user_id if referrer else None,
        acquisition_source="referral" if referrer else source,
    ))
    db.flush()
    return u
