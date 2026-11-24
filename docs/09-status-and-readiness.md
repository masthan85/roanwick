# Status, known limitations and production readiness

Written at the end of the first build. It separates what works and is tested from what is sandboxed, what needs outside credentials, and what is not built.

## Results

| Suite | Count | Result |
| --- | --- | --- |
| Backend (pytest, real PostgreSQL) | 73 | All pass |
| Frontend unit (vitest) | 8 | All pass |
| Browser end to end and accessibility (Playwright, Chromium) | 49 | All pass |
| TypeScript type check, production build | n/a | Clean |
| Alembic: apply to empty database, then `alembic check` | n/a | No drift |
| Lint (ruff) | n/a | Clean |

The automated accessibility scans (axe-core, WCAG 2.2 A and AA rules) found no serious or critical issues on 13 public pages and the signed-in customer, professional and admin screens. Automated tools find only a minority of real accessibility problems. This is a good floor, not a conformance claim.

Defects found and fixed while building: three database columns too narrow for values the code stored (found by tests and by the first live run); the customer acquisition cost showing zero when no marketing spend had been entered; a billing design that would have charged four weeks of plan visits at once; and a project-root mix-up between this app and an unrelated app in the same repository. In the second pass: reference data added in a later release never reached an existing installation because seeding stopped early (now idempotent per item); an automatic lint fix had removed an import that a new admin route needed; a payout note was overwritten after clawback netting; and a quality-review hook that I had applied by a text patch silently did not land, which the test for it caught. In the design pass: a plan-visits test that depended on the weekday it ran on, and browser tests that raced Next's streaming swap (fixed with a settle helper and proved stable over 40 runs).

## What exists

Customer website: registration, sign-in, password reset, profile and data export, saved addresses, postcode coverage with a waiting list, service pages with live pricing, itemised quotes, real availability, automatic matching or choosing a professional, booking with a held slot, test-mode payment with failure recovery, confirmation, status history, messaging, rescheduling, cancellation with the refund shown first, reviews, complaints, refund requests, favourites, recurring plans (pause, resume, skip, cancel), referral credit, promotional codes, payment history, notifications and support.

Professional portal: application, profile, services and areas, weekly hours and time off, document upload with expiry dates, a checklist, submission, job list with accept, decline, start and complete, messaging, earnings with commission shown per job, payout status, reviews and replies, performance metrics, expiry alerts and support.

Admin console: overview, bookings with manual assignment, professional verification and approval, complaints, refund requests, tickets, payouts, finance and growth reports, catalogue and price editing, coverage, promotions, manual costs, settings, flags, users and staff, audit log.

Added in the second pass, after a review against the original brief: service bundles priced and accounted for as platform-funded discounts; pre-filled rebooking with the same professional; creating new services and managing bundles from the admin console; a customer detail page; two-step verification for any account with an enforcement setting for staff; automatic professional quality reviews; clawback of professional-funded refunds after payout, netted from later payouts; erasure of a professional's documents when they close their account; retention jobs; and removal of the harmless 401 that anonymous visitors triggered on every page load.

Design refresh, built from `DESIGN.md`: a rebuilt landing page whose prices, cancellation tiers and pilot districts all come from the live API; self-hosted Fraunces and Inter fonts; a token layer for type, radius, shadow and the dark band section; SVG icons in place of text glyphs; clearer booking-step markers and bundle copy; and focus that moves to the next step after a postcode check. Checked on phone, tablet and desktop, in light and dark mode, and with the keyboard only.

Platform: 135 API operations with generated documentation, 50 tables, a payment abstraction with a sandbox and a Stripe adapter, idempotent webhooks, a job runner, structured logging, Docker and CI definitions.

## Completed, sandboxed and credential-dependent

| Capability | State |
| --- | --- |
| Booking, matching, double-booking protection, cancellations, refunds, payouts ledger, reports | Complete and tested |
| Card payments | Sandbox complete and tested. The Stripe adapter is written but has not been run against Stripe. It needs test-mode keys, and the browser needs Stripe's payment form (not built: the sandbox flow uses test card tokens). |
| Professional payouts | Ledger, hold and release logic complete. The transfer step is simulated in sandbox. Live payouts need Stripe Connect onboarding for professionals (not built; the profile only stores an account reference). |
| Email and SMS | Notifications are recorded and dispatched through an outbox. The console provider logs. SMTP and Twilio adapters are written and untested because no credentials were available. |
| Document storage | Local disk. Replace with object storage before more than one server runs. |
| Postcode lookup | Coverage by postcode district. An optional live lookup is not wired up. No map or distance-based coverage. |
| Docker images | Dockerfiles and compose file written and validated syntactically. Images were not built because no container daemon was available. |

## Not built, or only partly built

Coordinated multi-service bookings remain partial. Bundles give one booking a package of extras at a saving, and a customer's profile and addresses carry across services, but two different services (for example a clean and a handyman visit) are still booked separately, with separate payments. A true multi-service basket needs a booking group with one payment and back-to-back scheduling, which is only worth building once a second live category exists: today the only two services are cleaning. Maintenance care plans are not built (the flag exists and cannot be enabled). Real-time chat uses polling every ten seconds. There is no native app yet, but the API, token model and `X-Client: native` path are ready for one.

Matching uses rating and reliability to rank. Poor performance opens a review ticket for operations, using thresholds in settings, but never suspends anyone automatically. The withdrawal count is lifetime, not rolling, so an old record can keep a professional near the threshold.

Documents of professionals who stop working with us without closing their account are kept until a retention schedule exists. A clawback balance owed by a professional who never works again is not recovered. Two-step verification has no recovery codes: a lost device needs a database change.

## Known risks in the current build

Rate limiting is kept in each server process's memory, so with several API instances the effective limit is multiplied. Use a shared store before scaling out. Two-step verification is optional until `require_staff_mfa` is switched on, so switch it on before the pilot. Uploaded files are not virus scanned. Legal pages are drafts and say so on the page. The accessibility statement is aspirational until an independent audit. The Next.js build uses the new cache components model, so a future Next.js upgrade needs the build checked for new prerender rules.

## Production readiness checklist

Legal and commercial, all required before taking real bookings: solicitor review of terms, privacy notice and professional agreement; worker-status advice; insurance wording and requirements; consumer-rights review of cancellation terms; VAT and accounting advice; DPIA and ICO registration; Stripe and adviser confirmation of the payment structure; company details in the footer and legal pages.

Security and operations: set a strong `JWT_SECRET` and store secrets in a secret manager; HTTPS everywhere; switch on `require_staff_mfa` and have every staff member enrol; shared rate limiting; object storage with encryption and no public access; virus scanning on uploads; backups with a tested restore; an external penetration test; error tracking (set `SENTRY_DSN` and install the SDK); alarms on webhook failures, job failures and 5xx rates; a documented incident and data breach process.

Payments: run the Stripe adapter against test-mode keys; add Stripe's payment form to the checkout; build Connect onboarding for professionals; test refunds, disputes and failed transfers end to end; decide on negative balance handling.

Product: pilot with fewer professionals and districts than the full list; manual accessibility audit; email templates reviewed; support rota and response targets agreed; a process for the unassigned booking queue; a review of every customer-facing claim against what is actually checked.

## Decisions that need the founder

Brand name and domain. Pilot districts and starting number of professionals. Commission, booking fee and plan discounts. Whether enhanced DBS is mandatory. Whether public liability insurance should be mandatory (it is) or provided by the platform. Cancellation tiers and the payout hold. Charge-ahead window for plans (8 days) against reserving slots further ahead. Professional classification and contract after legal advice. Whether to build multi-service bundles or landlord and agent accounts first.

## Next development priorities

1. Stripe test-mode integration with the real payment form, and Connect onboarding.
2. Shared rate limiting, MFA recovery codes, object storage for documents and virus scanning.
3. Landlord and agent accounts with multi-property booking and invoices, which serve the end of tenancy segment.
4. A pay-later booking state so plan visits can be reserved further ahead and charged shortly before.
5. Booking groups and a multi-service basket, once a second service category is live.
6. A rolling window for the withdrawal metric, and a documented retention schedule for professional documents.
7. Native apps on the existing API.
