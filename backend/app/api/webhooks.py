from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.core.deps import DB
from app.services.payment_events import EventError, process_event
from app.services.payments import get_provider

router = APIRouter(tags=["Webhooks"])


@router.post("/webhooks/payments", summary="Payment provider webhook (signature verified, idempotent)")
async def payments_webhook(request: Request, db: DB, stripe_signature: str | None = Header(default=None), x_sandbox_signature: str | None = Header(default=None)):
    body = await request.body()
    prov = get_provider()
    event = prov.verify_webhook(body, stripe_signature if prov.name == "stripe" else x_sandbox_signature)
    try:
        outcome = process_event(db, event, prov.name)
    except EventError:
        # Return 5xx so the provider retries; the failed attempt is recorded and the transaction still commits that record.
        db.commit()
        return JSONResponse(status_code=500, content={"error": {"code": "event_failed", "message": "Event could not be processed. It will be retried."}})
    return {"received": True, "outcome": outcome}
