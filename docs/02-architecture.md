# Architecture and design decisions

## Shape of the system

Roanwick is a modular monolith with one PostgreSQL database. A Next.js application serves the customer website, the professional portal and the admin console. It talks to a FastAPI service over a single JSON API. Both services are stateless and can be scaled by adding containers. A small job runner executes the same Python code on a five-minute schedule.

```
Browser or future native app
        |
   Next.js 16 (React 19, Tailwind 4)         proxies /api/* to the API so the
        |                                    refresh cookie stays first-party
   FastAPI service  <---- webhooks ----  Payment provider (sandbox, or Stripe)
        |
   PostgreSQL 16  (btree_gist, citext)
        ^
   Job runner (python -m app.jobs, every 5 minutes)
```

The API code is organised by responsibility, not by technical layer:

- `app/models` holds the 50 tables, grouped into identity, catalogue, providers, bookings, finance, engagement and system.
- `app/services` holds the business rules: pricing, availability and matching, the booking lifecycle, payment events, finance and payouts, verification, recurring plans, reporting.
- `app/api` holds thin HTTP routers that validate input, check permissions and call services.
- `app/core` holds configuration, database sessions, security, error handling and permissions.

The rule of thumb is that a router never contains a business rule that another entry point (a job, a webhook, an admin action) might also need.

## Decisions and trade-offs

### 1. Modular monolith, not microservices

The booking, payment and payout flows must be transactionally consistent, and the team is small. A single deployable with clear module boundaries gives us that at the lowest cost. The seams that would be cut first if scale demanded it are notifications, reporting and document storage, which is why they are already behind their own functions.

### 2. FastAPI with synchronous SQLAlchemy

The workload is database-bound and the transactions are short. Synchronous endpoints run in a thread pool, which keeps transaction handling explicit and easy to reason about (one request, one transaction, commit on success). Moving to async later is a mechanical change if profiling ever justifies it. The trade-off is that very high concurrency needs more worker processes rather than more coroutines.

### 3. The database prevents double-booking

Application checks are not enough when two requests arrive together. The `bookings` table carries an exclusion constraint:

```
EXCLUDE USING gist (provider_id WITH =, tstzrange(starts_at, blocked_until, '[)') WITH &&)
WHERE status IN ('pending_payment','awaiting_provider','confirmed','in_progress')
```

`blocked_until` is the end of the visit plus the travel buffer, so the gap between jobs is enforced by the same rule. The service layer still checks availability first (to offer sensible alternatives), but if two transactions race, PostgreSQL rejects the second and the service tries the next candidate. A test fires eight simultaneous requests at one slot and asserts that exactly one succeeds. A second test inserts an overlapping row directly to prove the constraint holds without the application.

Unpaid bookings hold their slot for a configurable fifteen minutes. Expired holds are released lazily at the start of every availability search and booking, and by the job runner.

### 4. Money is integer pence, in one definition

All amounts are integers in pence. Reporting uses explicit definitions that are repeated in the admin console:

- Service value is labour, add-ons and plan discounts. It is the commission basis.
- Platform revenue is commission plus booking fees, less promotions that the platform funds.
- Contribution is platform revenue less card processing costs and platform-funded refunds.
- Gross booking value is cash taken from customers and is never presented as revenue.

Each booking's economics are written to `booking_financials` when it is finalised (completed, or a late cancellation is charged), so reports read stored facts and do not recompute from mutable settings.

### 5. Payments behind a provider interface

`PaymentProvider` has two implementations. The sandbox provider needs no credentials, behaves like a card processor in test mode (success, decline and insufficient-funds tokens), and produces the same webhook-shaped events a real processor would. The Stripe provider implements Connect-style separate charges and transfers. Both paths converge on one event handler, `process_event`, which is the only code that changes payment state.

That handler is idempotent. Every event is stored first, keyed by the provider's event id. A duplicate delivery is acknowledged and ignored. A failed delivery is recorded, the endpoint returns a 5xx so the provider retries, and the retry succeeds once the data it needs exists. The handler also rejects an event whose amount does not match the payment, and refunds a payment that arrives after the slot's hold has expired instead of keeping the money.

Idempotency keys are also accepted on booking creation and payment. The same key with the same request replays the stored response. The same key with a different request is rejected.

Funds flow in the intended live model: the customer is charged in full at booking, the platform holds the funds, and after completion plus a hold period it transfers the professional's share. This is a Stripe Connect "separate charges and transfers" pattern. Whether it needs a different structure for regulatory reasons is a question for Stripe and an adviser (see the compliance register).

### 6. Authentication and authorisation

Authentication is built from established parts: Argon2id password hashing (pwdlib), short-lived signed access tokens (PyJWT), rotating opaque refresh tokens stored only as SHA-256 hashes, and optional time-based one-time passwords (RFC 6238, checked against the standard test vector) for two-step verification. Any account can enrol with an authenticator app. A business setting, `require_staff_mfa`, blocks staff who have not enrolled from every admin action until they do. Replaying a refresh token that has already been rotated is treated as theft and revokes every session for that user. Accounts lock for 15 minutes after five failed sign-ins. Sign-in errors are generic, and password reset always returns the same response whether or not the account exists.

Browsers receive the refresh token as an `HttpOnly`, `SameSite=Lax` cookie scoped to the auth path, and keep the access token in memory only. A native app sends `X-Client: native` and receives the refresh token in the response body for secure storage. That is the path to iOS and Android.

Authorisation has two layers. Roles are `customer` and `provider` for the public apps, and `super_admin`, `operations`, `support` and `finance` for staff. Staff roles map to named permissions through the `role_permissions` table, and every admin route declares the permission it needs. Data isolation for customers and professionals is enforced in the query layer (a booking is only returned to its own customer or professional), and a test suite checks that cross-account access returns 404 rather than leaking existence.

Every staff mutation writes an audit event with the actor, role, entity, before and after values, IP and request id. Opening a provider's identity document is itself audited.

### 7. Verification is data, not a label

A professional can only be approved if every mandatory document for every service they offer is approved and in date. The requirements are rows in `category_requirements`. Customer-facing badges are generated from approved, unexpired documents only. If an insurance certificate expires, the professional silently drops out of availability, matching and the public profile until a replacement is approved. Regulated categories (plumbing, electrical, gas and heating) are seeded switched off and flagged for compliance review. The admin console and the API both refuse to enable one until its requirements exist and a person has confirmed they were reviewed.

### 8. Next.js 16 with a client-side data layer

Marketing and legal pages are statically prerendered with metadata and structured data for search. Signed-in screens fetch from the API in the browser, which keeps the sensitive paths simple. The project pins its own Turbopack root because it lives inside a repository that contains an unrelated application.

### 9. Time handling

All timestamps are stored in UTC. Professionals' working hours are stored as local Europe/London times and converted per date using the IANA time zone, so daylight saving changes do not shift a working day. The web app formats every date and time in Europe/London, composed from parts so that output does not vary between browsers.

### 10. What was deliberately left out of the MVP

Kubernetes, a message broker, a search engine, a feature-flag service and machine learning are not used. The job runner is a loop around a function. Feature flags are a table. Matching is a transparent ranking (requested professional, then favourites, then rating and punctuality). Quality management is a set of thresholds in settings (withdrawals, late-start rate, average rating, serious complaints). Crossing one opens a review ticket for operations and never suspends anyone automatically. These can be replaced when there is evidence that they are the constraint.

## Booking and payment workflow

1. The customer enters a postcode and options. `POST /quotes` returns an itemised, expiring quotation, and the cancellation terms in force are snapshotted into it.
2. `GET /catalogue/slots` returns only start times at which at least one eligible professional is free, after working hours, time off, existing bookings and travel buffers.
3. `POST /bookings` re-validates everything inside a transaction, ranks candidate professionals, inserts the booking and lets the exclusion constraint settle any race. The booking is `pending_payment` and the slot is held.
4. Payment is confirmed (sandbox: `POST /bookings/{id}/pay`, live: the browser confirms with Stripe and the webhook arrives). The event handler marks the payment succeeded and moves the booking to `confirmed`, or to `awaiting_provider` if the professional reviews each job.
5. The professional starts and completes the job. On completion the system writes the booking's economics, creates a payout with a release date after the hold period, prompts the customer for a review and triggers referral credit if it was their first visit.
6. The payout job pays out due payouts, except where a complaint or refund request is open on the booking.

Cancellation follows the configured tiers. A customer cancelling late can forfeit part of the price. The retained amount is treated as service value and the professional is compensated from it. A professional cancelling, or the platform cancelling, always refunds in full. When a professional declines or withdraws, the system tries to re-match, and if nobody is free it leaves the booking unassigned for operations and tells the customer.

Allowed status changes:

```
pending_payment -> awaiting_provider | confirmed | expired | cancelled
awaiting_provider -> confirmed | cancelled
confirmed -> in_progress | completed | cancelled
in_progress -> completed | cancelled
```

## Infrastructure plan

The aim is the lowest running cost that still has backups, TLS and a sensible failure story.

Pilot (a few hundred bookings a month): one small managed PostgreSQL instance with automated backups, the API and job runner as two small container tasks, the web app as one container, object storage for documents, and a managed load balancer or edge service for TLS. On AWS that is RDS PostgreSQL (db.t4g.small, single-AZ with point-in-time recovery), ECS on Fargate or App Runner, S3 for documents with server-side encryption and no public access, ALB or CloudFront, Secrets Manager, and CloudWatch for logs and alarms. Expect a low three-figure monthly cost. Azure has direct equivalents (Flexible Server, Container Apps, Blob Storage, Key Vault).

Before live traffic: move rate limiting from per-process memory to a shared store, add multi-factor authentication for staff, run an external penetration test, and enable error tracking (the API reads `SENTRY_DSN` if set).

Monitoring: the API writes one structured JSON log line per request with a request id (also returned in the `X-Request-ID` header and in every error body), `/health` and `/ready` support load balancer checks, and the admin operations report is the business-level monitor. Alert on 5xx rate, job runner failures, failed webhook events (`webhook_events.status = 'failed'`), queued notifications older than ten minutes, and payouts held longer than expected.
