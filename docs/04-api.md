# API guide

The API is documented interactively at `/api/docs` (Swagger UI) when the service is running, and the machine-readable contract is committed as [openapi.json](openapi.json). It currently exposes 135 operations on 120 paths under `/api/v1`. Regenerate the file with the snippet in the deployment guide whenever routes change.

## Conventions

Amounts are integer pence (GBP). Timestamps are ISO 8601 with an offset. Dates and times a customer sees are UK local time. Identifiers are UUIDs. Lists are paginated with `page` (from 1) and `page_size` (1 to 100) and return `{ items, total, page, page_size }`.

Errors always have the same shape, so clients can handle them in one place:

```json
{ "error": { "code": "no_availability", "message": "No professional is available at that time. Please choose another slot.", "details": {}, "request_id": "9a8949fffea94bde" } }
```

Validation failures return 422 with `code: "validation_error"` and a list of `{ field, message }` under `details.fields`. The `request_id` matches the `X-Request-ID` response header and the server log line, which makes support investigations quick.

Authentication uses a bearer access token. Send `Idempotency-Key: <unique value>` on `POST /bookings` and `POST /bookings/{id}/pay`. Repeating a request with the same key replays the original response. Reusing a key for a different request returns 409 `idempotency_key_reused`.

## Groups

| Group | Purpose |
| --- | --- |
| Authentication | Register, sign in (with an optional authenticator code), refresh, sign out, profile, password change and reset, email verification, two-step verification setup, data export and account closure |
| Public | Configuration, coverage check, waiting list, catalogue, bundles, slot search, quotations, available professionals, public profiles, contact form |
| Customer | Addresses, bookings (create, pay, cancel, reschedule), reviews, complaints, refund requests, favourites, recurring plans, referrals, payments, notifications |
| Service professional | Application, profile, services and areas, availability and time off, documents, checklist and submission, jobs and their lifecycle, earnings, reviews, metrics |
| Messaging | Messages between customer and professional on a booking, readable by authorised staff |
| Administration | Users, customer detail and staff, provider verification and approval, bookings and assignment, complaints, refund requests, refunds, payouts and adjustments, catalogue (including creating services), bundles, coverage, promotions, settings and flags, costs, reports, audit log, scheduled jobs |
| Webhooks | Signed payment events |

## Webhooks

`POST /api/v1/webhooks/payments` accepts payment events. In sandbox mode the body is signed with HMAC-SHA256 using `SANDBOX_WEBHOOK_SECRET` and sent in `X-Sandbox-Signature`. In Stripe mode the standard `Stripe-Signature` header is verified with `STRIPE_WEBHOOK_SECRET`. Handled events are `payment_intent.succeeded`, `payment_intent.payment_failed` and `charge.refunded`. The endpoint returns 200 for processed or duplicate events and 500 for a failure that should be retried.

## Permissions

Every administration route names the permission it needs. The permission list and the default role mapping are in `backend/app/core/permissions.py` and are copied into the database by the seed command.

| Role | Permissions |
| --- | --- |
| super_admin | all |
| operations | users.read, users.manage, providers.review, bookings.read, bookings.manage, complaints.manage, coverage.manage, payouts.read |
| support | users.read, bookings.read, complaints.manage, refunds.manage |
| finance | bookings.read, refunds.manage, payouts.read, payouts.manage, finance.read, finance.manage |

## Using the API from a native app

Send `X-Client: native` on sign-in, registration and refresh. The response then includes `refresh_token` in the body. Store it in the platform keychain, and call `POST /auth/refresh` with `{ "refresh_token": "..." }` when the access token expires. Refresh tokens rotate on every use.
