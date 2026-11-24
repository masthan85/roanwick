import hashlib
import json
from collections.abc import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.models.system import IdempotencyRecord


def request_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def run_idempotent(db: Session, scope: str, key: str | None, payload: dict, fn: Callable[[], dict]) -> dict:
    """Run fn once per (scope, key). A repeat with the same payload replays the stored response;
    the same key with a different payload is rejected."""
    if not key:
        return fn()
    h = request_hash(payload)
    rec = db.get(IdempotencyRecord, (key, scope))
    if rec is None:
        try:
            with db.begin_nested():
                rec = IdempotencyRecord(key=key, scope=scope, request_hash=h)
                db.add(rec)
                db.flush()
        except IntegrityError:
            rec = db.get(IdempotencyRecord, (key, scope))
            if rec is None:
                raise Conflict("Please retry this request.", code="idempotency_race")
        else:
            result = fn()
            rec.response = result
            rec.status_code = 200
            db.flush()
            return result
    if rec.request_hash != h:
        raise Conflict("This Idempotency-Key was already used with a different request.", code="idempotency_key_reused")
    if rec.response is None:
        raise Conflict("A request with this key is still being processed.", code="idempotency_in_progress")
    return rec.response
