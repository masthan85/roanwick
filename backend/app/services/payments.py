"""Payment provider abstraction.

SandboxProvider needs no credentials and behaves like a card processor in test mode.
StripeProvider uses Stripe Connect (separate charges and transfers) and needs real keys; it has not been
exercised against Stripe from this environment and must be tested with test-mode keys before pilot use.
"""
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.errors import AppError, Unprocessable


@dataclass
class Intent:
    external_id: str
    client_secret: str | None


class PaymentProvider:
    name = "base"

    def create_intent(self, amount_pence: int, *, booking_ref: str, customer_email: str, idempotency_key: str, saved_method: str | None = None) -> Intent: ...
    def confirm(self, external_id: str, payment_method: str, amount_pence: int) -> dict:
        """Sandbox only: returns a webhook-shaped event. Stripe confirms client-side and reports by webhook."""
        raise NotImplementedError
    def refund(self, payment_external_id: str, amount_pence: int, idempotency_key: str) -> str: ...
    def transfer(self, account_id: str | None, amount_pence: int, idempotency_key: str, booking_ref: str) -> str: ...
    def verify_webhook(self, body: bytes, signature: str | None) -> dict: ...


SANDBOX_CARDS = {
    "pm_card_visa": None,
    "pm_card_mastercard": None,
    "pm_card_declined": "Your card was declined.",
    "pm_card_insufficient_funds": "Your card has insufficient funds.",
    "pm_card_expired": "Your card has expired.",
}


def sign_sandbox(body: bytes) -> str:
    return hmac.new(get_settings().sandbox_webhook_secret.encode(), body, hashlib.sha256).hexdigest()


class SandboxProvider(PaymentProvider):
    name = "sandbox"

    def create_intent(self, amount_pence, *, booking_ref, customer_email, idempotency_key, saved_method=None) -> Intent:
        # Deterministic from the idempotency key so a retry cannot create a second intent.
        ident = uuid.uuid5(uuid.NAMESPACE_URL, f"intent:{idempotency_key}").hex[:20]
        return Intent(f"pi_sbx_{ident}", f"pi_sbx_{ident}_secret")

    def confirm(self, external_id, payment_method, amount_pence) -> dict:
        if payment_method not in SANDBOX_CARDS:
            raise Unprocessable("Unknown sandbox payment method. Use pm_card_visa or pm_card_declined.", code="bad_payment_method")
        failure = SANDBOX_CARDS[payment_method]
        eid = f"evt_sbx_{uuid.uuid5(uuid.NAMESPACE_URL, f'{external_id}:{payment_method}:{uuid.uuid4()}').hex[:16]}"
        if failure:
            return {"id": eid, "type": "payment_intent.payment_failed", "data": {"external_id": external_id, "message": failure}}
        get_settings()
        fee = round(amount_pence * 150 / 10000) + 20  # sandbox reports the same shape Stripe's balance transaction would
        return {"id": eid, "type": "payment_intent.succeeded", "data": {"external_id": external_id, "amount": amount_pence, "fee": fee}}

    def refund(self, payment_external_id, amount_pence, idempotency_key) -> str:
        return f"re_sbx_{uuid.uuid5(uuid.NAMESPACE_URL, f'refund:{idempotency_key}').hex[:18]}"

    def transfer(self, account_id, amount_pence, idempotency_key, booking_ref) -> str:
        return f"tr_sbx_{uuid.uuid5(uuid.NAMESPACE_URL, f'transfer:{idempotency_key}').hex[:18]}"

    def verify_webhook(self, body, signature) -> dict:
        if not signature or not hmac.compare_digest(signature, sign_sandbox(body)):
            raise AppError("Invalid webhook signature.", code="bad_signature", status_code=400)
        return json.loads(body)


class StripeProvider(PaymentProvider):
    name = "stripe"

    def __init__(self) -> None:
        import stripe

        s = get_settings()
        if not s.stripe_secret_key:
            raise RuntimeError("STRIPE_SECRET_KEY is required when PAYMENT_PROVIDER=stripe")
        stripe.api_key = s.stripe_secret_key
        self.stripe = stripe

    def create_intent(self, amount_pence, *, booking_ref, customer_email, idempotency_key, saved_method=None) -> Intent:
        params = dict(
            amount=amount_pence, currency="gbp", receipt_email=customer_email,
            metadata={"booking_ref": booking_ref}, transfer_group=booking_ref,
        )
        if saved_method:
            params.update(payment_method=saved_method, confirm=True, off_session=True)
        else:
            params["automatic_payment_methods"] = {"enabled": True}
        pi = self.stripe.PaymentIntent.create(**params, idempotency_key=idempotency_key)
        return Intent(pi["id"], pi.get("client_secret"))

    def refund(self, payment_external_id, amount_pence, idempotency_key) -> str:
        r = self.stripe.Refund.create(payment_intent=payment_external_id, amount=amount_pence, idempotency_key=idempotency_key)
        return r["id"]

    def transfer(self, account_id, amount_pence, idempotency_key, booking_ref) -> str:
        if not account_id:
            raise AppError("Provider has no connected payout account.", code="no_payout_account", status_code=422)
        t = self.stripe.Transfer.create(
            amount=amount_pence, currency="gbp", destination=account_id, transfer_group=booking_ref, idempotency_key=idempotency_key
        )
        return t["id"]

    def verify_webhook(self, body, signature) -> dict:
        try:
            ev = self.stripe.Webhook.construct_event(body, signature, get_settings().stripe_webhook_secret)
        except Exception as exc:
            raise AppError("Invalid webhook signature.", code="bad_signature", status_code=400) from exc
        obj = ev["data"]["object"]
        kind = ev["type"]
        if kind == "payment_intent.succeeded":
            return {"id": ev["id"], "type": kind, "data": {"external_id": obj["id"], "amount": obj["amount_received"], "fee": None}}
        if kind == "payment_intent.payment_failed":
            msg = (obj.get("last_payment_error") or {}).get("message", "Payment failed.")
            return {"id": ev["id"], "type": kind, "data": {"external_id": obj["id"], "message": msg}}
        if kind == "charge.refunded":
            return {"id": ev["id"], "type": kind, "data": {"external_id": obj.get("payment_intent"), "refunded": obj.get("amount_refunded")}}
        return {"id": ev["id"], "type": kind, "data": {}}


_provider: PaymentProvider | None = None


def get_provider() -> PaymentProvider:
    global _provider
    if _provider is None or _provider.name != get_settings().payment_provider:
        _provider = StripeProvider() if get_settings().payment_provider == "stripe" else SandboxProvider()
    return _provider
