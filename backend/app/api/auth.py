import uuid
from datetime import timedelta

import jwt
from fastapi import APIRouter, Cookie, Header, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.deps import DB, CurrentUser, audit, user_permissions
from app.core.errors import AppError, Conflict, Forbidden, Unauthorised, Unprocessable
from app.core.ratelimit import limiter
from app.core.security import (
    create_access_token, create_purpose_token, decode_token, hash_password, hash_token, new_refresh_token, verify_password,
)
from app.models.identity import Address, RefreshToken, User
from app.services import accounts, mfa
from app.services.notify import notify

router = APIRouter(prefix="/auth", tags=["Authentication"])
COOKIE = "rw_refresh"
COMMON = {"password", "password123", "qwerty123456", "1234567890", "letmein1234"}


def _check_password(v: str) -> str:
    if len(v) < 10:
        raise ValueError("Use at least 10 characters.")
    if v.lower() in COMMON or v.lower().isalpha() and len(set(v)) < 5:
        raise ValueError("That password is too easy to guess.")
    return v


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, pattern=r"^(\+44|0)[0-9 ]{9,13}$")
    accept_terms: bool
    marketing_consent: bool = False
    referral_code: str | None = None
    source: str = Field(default="direct", max_length=40)

    _pw = field_validator("password")(_check_password)

    @field_validator("accept_terms")
    @classmethod
    def _terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You need to accept the terms to create an account.")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    mfa_code: str | None = Field(default=None, max_length=10)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None  # returned only to native clients (X-Client: native)
    user: dict


def user_dict(db, u: User) -> dict:
    return {
        "id": str(u.id), "email": u.email, "full_name": u.full_name, "phone": u.phone, "roles": u.role_keys,
        "email_verified": u.email_verified_at is not None, "marketing_consent": u.marketing_consent, "mfa_enabled": u.mfa_enabled_at is not None,
        "permissions": sorted(user_permissions(db, u)) if any(r.is_staff for r in u.roles) else [],
    }


def issue_tokens(db, u: User, request: Request, response: Response, native: bool) -> TokenOut:
    s = get_settings()
    raw, hashed = new_refresh_token()
    db.add(RefreshToken(user_id=u.id, token_hash=hashed, expires_at=utcnow() + timedelta(days=s.refresh_token_days), user_agent=(request.headers.get("user-agent") or "")[:300]))
    response.set_cookie(COOKIE, raw, max_age=s.refresh_token_days * 86400, httponly=True, secure=s.is_production, samesite="lax", path="/api/v1/auth")
    # A non-secret hint so the browser only tries to refresh when a session might exist (avoids a 401 on every anonymous page view).
    response.set_cookie("rw_session", "1", max_age=s.refresh_token_days * 86400, httponly=False, secure=s.is_production, samesite="lax", path="/")
    return TokenOut(
        access_token=create_access_token(u.id, u.role_keys), expires_in=s.access_token_minutes * 60,
        refresh_token=raw if native else None, user=user_dict(db, u),
    )


@router.post("/register", response_model=TokenOut, status_code=201, summary="Create a customer account")
@limiter.limit("10/hour")
def register(body: RegisterIn, request: Request, response: Response, db: DB, x_client: str | None = Header(default=None)):
    u = accounts.create_customer(
        db, email=body.email, password=body.password, full_name=body.full_name, phone=body.phone,
        marketing=body.marketing_consent, referral_code=body.referral_code, source=body.source,
    )
    token = create_purpose_token(u.id, "verify_email", 60 * 24 * 3)
    notify(db, u, "verify_email", "Confirm your email address", f"Welcome to Roanwick. Confirm your email: {get_settings().public_web_url}/verify-email?token={token}", ("email",))
    audit(db, request, u, "auth.register", "user", u.id)
    return issue_tokens(db, u, request, response, x_client == "native")


@router.post("/login", response_model=TokenOut, summary="Sign in with email and password")
@limiter.limit("20/minute")
def login(body: LoginIn, request: Request, response: Response, db: DB, x_client: str | None = Header(default=None)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    now = utcnow()
    generic = Unauthorised("Email or password is incorrect.")
    if u is None or not u.password_hash:
        verify_password(body.password, "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")  # equalise timing
        raise generic
    if u.locked_until and u.locked_until > now:
        raise AppError("Too many attempts. Try again in a few minutes.", code="account_locked", status_code=429)
    if not verify_password(body.password, u.password_hash):
        u.failed_logins += 1
        if u.failed_logins >= 5:
            u.locked_until, u.failed_logins = now + timedelta(minutes=15), 0
            audit(db, request, None, "auth.locked", "user", u.id)
        db.commit()  # persist the counter even though we are about to raise
        raise generic
    if not u.is_active or u.anonymised_at:
        raise Forbidden("This account has been deactivated. Please contact support.")
    if u.mfa_enabled_at and u.mfa_secret:
        if not body.mfa_code:
            raise AppError("Enter the 6-digit code from your authenticator app.", code="mfa_required", status_code=401)
        if not mfa.verify(u.mfa_secret, body.mfa_code):
            u.failed_logins += 1
            if u.failed_logins >= 5:
                u.locked_until, u.failed_logins = now + timedelta(minutes=15), 0
            db.commit()
            raise AppError("That code is not correct, or has expired.", code="mfa_invalid", status_code=401)
    u.failed_logins, u.locked_until, u.last_login_at = 0, None, now
    audit(db, request, u, "auth.login", "user", u.id)
    return issue_tokens(db, u, request, response, x_client == "native")


class RefreshIn(BaseModel):
    refresh_token: str | None = None


@router.post("/refresh", response_model=TokenOut, summary="Exchange a refresh token for a new access token (rotating)")
def refresh(request: Request, response: Response, db: DB, body: RefreshIn | None = None, rw_refresh: str | None = Cookie(default=None), x_client: str | None = Header(default=None)):
    raw = (body.refresh_token if body else None) or rw_refresh
    if not raw:
        raise Unauthorised("Please sign in again.")
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)).with_for_update())
    if rt is None or rt.expires_at < utcnow():
        raise Unauthorised("Please sign in again.")
    if rt.revoked_at is not None:
        # Reuse of a rotated token suggests theft: revoke every session for this user.
        for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == rt.user_id, RefreshToken.revoked_at.is_(None))):
            t.revoked_at = utcnow()
        db.commit()
        raise Unauthorised("Please sign in again.")
    u = db.get(User, rt.user_id)
    if not u or not u.is_active:
        raise Unauthorised("Please sign in again.")
    rt.revoked_at = utcnow()
    return issue_tokens(db, u, request, response, x_client == "native")


@router.post("/logout", status_code=204)
def logout(response: Response, db: DB, rw_refresh: str | None = Cookie(default=None)):
    if rw_refresh:
        rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(rw_refresh)))
        if rt and not rt.revoked_at:
            rt.revoked_at = utcnow()
    response.delete_cookie(COOKIE, path="/api/v1/auth")
    response.delete_cookie("rw_session", path="/")


@router.get("/me", summary="The signed-in user")
def me(user: CurrentUser, db: DB):
    return user_dict(db, user)


class ProfileIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, pattern=r"^(\+44|0)[0-9 ]{9,13}$")
    marketing_consent: bool | None = None


@router.patch("/me")
def update_me(body: ProfileIn, user: CurrentUser, db: DB):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    return user_dict(db, user)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str
    _pw = field_validator("new_password")(_check_password)


@router.post("/change-password", status_code=204)
def change_password(body: PasswordChangeIn, user: CurrentUser, db: DB, request: Request):
    if not verify_password(body.current_password, user.password_hash or ""):
        raise Unprocessable("Your current password is not correct.", code="wrong_password")
    user.password_hash = hash_password(body.new_password)
    for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))):
        t.revoked_at = utcnow()
    audit(db, request, user, "auth.password_changed", "user", user.id)


class ForgotIn(BaseModel):
    email: EmailStr


@router.post("/forgot-password", status_code=202, summary="Request a password reset email")
@limiter.limit("5/hour")
def forgot(body: ForgotIn, request: Request, db: DB):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if u and u.is_active:
        token = create_purpose_token(u.id, "reset_password", 60)
        notify(db, u, "password_reset", "Reset your Roanwick password", f"Reset your password within one hour: {get_settings().public_web_url}/reset-password?token={token}", ("email",))
    return {"message": "If an account exists for that address, we have sent a reset link."}  # same response either way


class ResetIn(BaseModel):
    token: str
    new_password: str
    _pw = field_validator("new_password")(_check_password)


@router.post("/reset-password", status_code=204)
def reset(body: ResetIn, db: DB):
    try:
        payload = decode_token(body.token, "reset_password")
    except jwt.PyJWTError:
        raise Unprocessable("This reset link is invalid or has expired.", code="bad_token")
    u = db.get(User, uuid.UUID(payload["sub"]))
    if not u:
        raise Unprocessable("This reset link is invalid or has expired.", code="bad_token")
    u.password_hash = hash_password(body.new_password)
    u.failed_logins, u.locked_until = 0, None
    for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == u.id, RefreshToken.revoked_at.is_(None))):
        t.revoked_at = utcnow()


class VerifyIn(BaseModel):
    token: str


@router.post("/verify-email", status_code=204)
def verify_email(body: VerifyIn, db: DB):
    try:
        payload = decode_token(body.token, "verify_email")
    except jwt.PyJWTError:
        raise Unprocessable("This link is invalid or has expired.", code="bad_token")
    u = db.get(User, uuid.UUID(payload["sub"]))
    if u and not u.email_verified_at:
        u.email_verified_at = utcnow()


@router.get("/me/export", summary="Download your personal data (UK GDPR right of access)")
def export_data(user: CurrentUser, db: DB):
    from app.models.bookings import Booking
    from app.models.engagement import Notification, Review

    addresses = db.scalars(select(Address).where(Address.user_id == user.id)).all()
    bookings = db.scalars(select(Booking).where((Booking.customer_id == user.id) | (Booking.provider_id == user.id))).all()
    reviews = db.scalars(select(Review).where(Review.customer_id == user.id)).all()
    return {
        "account": {"email": user.email, "full_name": user.full_name, "phone": user.phone, "created_at": user.created_at, "marketing_consent": user.marketing_consent},
        "addresses": [{"line1": a.line1, "line2": a.line2, "city": a.city, "postcode": a.postcode, "access_notes": a.access_notes} for a in addresses],
        "bookings": [{"reference": b.reference, "status": b.status, "starts_at": b.starts_at, "total_pence": b.total_pence} for b in bookings],
        "reviews": [{"rating": r.rating, "comment": r.comment, "created_at": r.created_at} for r in reviews],
        "notification_count": db.query(Notification).filter(Notification.user_id == user.id).count(),
        "note": "Financial records are retained for statutory periods and are not included in erasure requests.",
    }


class DeleteIn(BaseModel):
    password: str


def erase_provider_data(db, user_id) -> int:
    """Remove a professional's identity documents and personal profile text. Booking and payout records stay for statutory retention."""
    from app.models.providers import ProviderDocument, ProviderProfile
    from app.services import storage

    prof = db.get(ProviderProfile, user_id)
    if prof is None:
        return 0
    docs = db.scalars(select(ProviderDocument).where(ProviderDocument.provider_id == user_id)).all()
    for d in docs:
        storage.delete_file(d.storage_key)
        db.delete(d)
    prof.display_name, prof.bio, prof.languages = "Former professional", "", []
    prof.status, prof.status_reason, prof.accepts_jobs = "suspended", "Account closed", False
    return len(docs)


@router.post("/me/delete", status_code=204, summary="Close and anonymise your account (UK GDPR right to erasure)")
def delete_account(body: DeleteIn, user: CurrentUser, db: DB, request: Request):
    from app.models.bookings import Booking, BLOCKING_STATUSES

    if not verify_password(body.password, user.password_hash or ""):
        raise Unprocessable("Your password is not correct.", code="wrong_password")
    open_jobs = db.query(Booking).filter(((Booking.customer_id == user.id) | (Booking.provider_id == user.id)), Booking.status.in_(BLOCKING_STATUSES)).count()
    if open_jobs:
        raise Conflict("Please cancel or complete your upcoming bookings before closing your account.", code="open_bookings")
    user.email = f"deleted-{user.id.hex}@anonymised.invalid"
    user.full_name, user.phone, user.password_hash = "Deleted user", None, None
    user.is_active, user.anonymised_at, user.marketing_consent = False, utcnow(), False
    for a in db.scalars(select(Address).where(Address.user_id == user.id)):
        a.line1, a.line2, a.access_notes, a.postcode = "Removed", None, None, a.outward_code
    for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)):
        t.revoked_at = utcnow()
    erase_provider_data(db, user.id)
    audit(db, request, user, "auth.account_erased", "user", user.id)


@router.post("/mfa/setup", summary="Start authenticator-app enrolment. Returns the key to add to the app")
def mfa_setup(user: CurrentUser, db: DB):
    if user.mfa_enabled_at:
        raise Conflict("Two-step verification is already on. Turn it off first to enrol a new device.", code="mfa_already_enabled")
    user.mfa_secret = mfa.new_secret()
    return {"secret": user.mfa_secret, "otpauth_uri": mfa.provisioning_uri(user.mfa_secret, user.email)}


class MfaCodeIn(BaseModel):
    code: str = Field(max_length=10)


@router.post("/mfa/enable", summary="Confirm enrolment with a code from the app")
def mfa_enable(body: MfaCodeIn, request: Request, user: CurrentUser, db: DB):
    if not user.mfa_secret or user.mfa_enabled_at:
        raise Conflict("Start setup first.", code="mfa_not_pending")
    if not mfa.verify(user.mfa_secret, body.code):
        raise Unprocessable("That code is not correct. Check the time on your device and try again.", code="mfa_invalid")
    user.mfa_enabled_at = utcnow()
    audit(db, request, user, "auth.mfa_enabled", "user", user.id)
    return {"mfa_enabled": True}


class MfaDisableIn(BaseModel):
    password: str
    code: str = Field(max_length=10)


@router.post("/mfa/disable", status_code=204)
def mfa_disable(body: MfaDisableIn, request: Request, user: CurrentUser, db: DB):
    if not user.mfa_enabled_at or not user.mfa_secret:
        raise Conflict("Two-step verification is not on.", code="mfa_not_enabled")
    if not verify_password(body.password, user.password_hash or "") or not mfa.verify(user.mfa_secret, body.code):
        raise Unprocessable("Your password or code is not correct.", code="mfa_invalid")
    user.mfa_secret, user.mfa_enabled_at = None, None
    audit(db, request, user, "auth.mfa_disabled", "user", user.id)
