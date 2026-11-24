# Data model

The schema is created by two Alembic migrations (`0001_initial_schema`, `0002_bundles_adjustments_staff_mfa`) and has 50 tables. Running `alembic check` in CI confirms that the migrations and the SQLAlchemy models never drift apart. The model code lives in `backend/app/models`.

PostgreSQL extensions used: `btree_gist` (the double-booking constraint) and `citext` (case-insensitive email addresses).

## Identity and access

`users` holds one row per person, with an Argon2id password hash, lockout counters, an optional two-step verification secret and enrolment time, and an `anonymised_at` marker used when an account is erased. `roles`, `permissions`, `role_permissions` and `user_roles` implement role-based access. `refresh_tokens` stores only hashes of refresh tokens. `customer_profiles` carries the referral code, acquisition source, account credit balance and who referred the customer. `addresses` stores customer addresses with the postcode district split out for coverage checks.

## Catalogue and pricing

`service_categories` and `service_offerings` describe what can be booked. A category has `is_active` and `requires_compliance_review`. An offering is priced `hourly` (rate, minimum, maximum, step) or `tiered` (by bedrooms). `offering_addons`, `price_tiers` and `frequency_discounts` hold the options and discounts. `category_requirements` lists the documents a professional must hold for a category. `bundles` are priced packages of extras on one service, with a platform-funded percentage discount. `service_areas` is the list of postcode districts we serve. `quotations` and `quotation_lines` are immutable price quotes with the cancellation terms snapshotted into them.

## Professionals

`provider_profiles` holds the public profile, approval status (`draft`, `submitted`, `approved`, `rejected`, `suspended`), quality counters, optional commission override and the connected payout account reference. `provider_services` and `provider_areas` say what they offer and where. `availability_rules` (weekly working hours in London local time) and `availability_exceptions` (time off or extra hours on a date) describe when. `provider_documents` records each uploaded document, its review decision, reviewer and expiry date.

## Bookings

`bookings` is the central table: customer, professional, offering, quotation, time range, status, an address snapshot, the cancellation terms that applied and the idempotency key. Its exclusion constraint prevents overlapping active bookings for a professional. `booking_lines` copies the quote lines. `booking_status_history` records every transition with the actor and a note. `booking_messages` holds the conversation. `subscriptions` holds recurring plans. `favourite_providers` holds saved professionals.

## Money

`payments` records each charge with the provider reference, status, the card amount and the account credit applied. `refunds` records each refund, who funded it (customer policy, platform or professional) and its reason. `refund_requests` is the customer-initiated request queue. `payouts` has one row per booking with the commission and the professional's net amount, a release date and a status. `booking_financials` stores the per-booking economics used by every report, with the processing fee marked `actual` or `estimated`. `provider_adjustments` records money a professional owes the platform (for example a refund they funded after their payout was paid), netted off their next payouts. `business_costs` holds manually entered operating costs and is reported separately from transactions.

`credit_transactions` is the ledger behind a customer's account credit (referral rewards, spend, refunds). `promotions` and `promotion_redemptions` implement discount codes.

## Quality and support

`reviews` (one per completed booking, with rating, punctuality and a professional's reply), `complaints` (category, severity, status and outcome) and `support_tickets` (general contact, professional disputes, payout and account queries).

## Platform

`notifications` is both the in-app inbox and the email and SMS outbox, with a status that the job runner advances. `audit_events` is the append-only record of staff and sensitive actions. `feature_flags` and `app_settings` hold business configuration (commission, fees, cancellation tiers, hold periods, and so on). `idempotency_records` and `webhook_events` make retries safe. `metric_events` records funnel events such as quotes created and waiting-list sign-ups.

## Integrity rules worth knowing

Referential integrity is enforced with foreign keys throughout. Amounts are non-negative integers by convention and validated in the API. A booking cannot end before it starts, and its blocked window cannot be shorter than the visit. A review is unique per booking, a payout is unique per booking, and a customer cannot reuse an idempotency key for a different booking. Reports never read mutable configuration to recompute history. They read the values that were stored when the booking was finalised.
