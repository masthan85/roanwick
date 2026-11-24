# Roanwick: Product Strategy and Requirements (Phase 1)

Status: working draft for founder review. Roanwick is a working name; check trade mark and domain availability before using it publicly.

Important caveat. The Urban Company UK research report referred to in the brief was not present in the repository or the conversation. Every market figure below is therefore an explicit assumption, not a finding. Each is stored as configuration in the platform (see `docs/05-commercial-model.md`) and should be replaced with validated numbers from the London pilot.

## 1. The three strongest opportunities

Scored on demand, competitive intensity, willingness to pay, repeat frequency, operational complexity and contribution margin. Scores are 1 to 5 and are judgement, not data.

| Opportunity | Demand | Competition gap | Repeat | Ops complexity (5 = simple) | Margin | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| Recurring domestic cleaning with a named, consistent cleaner | 5 | 3 | 5 | 4 | 3 | Launch wedge |
| End-of-tenancy cleaning for tenants, landlords and letting agents | 4 | 3 | 2 (but agent repeat is high) | 4 | 4 | Second wedge, same supply |
| Preventative home maintenance plans (handyman, gutters, boiler service) | 3 | 4 | 4 | 1 (gas and electrical are regulated) | 3 | Defer until compliance is defined |

Why cleaning first. Cleaning is not a legally regulated trade, so verification is identity, right to work and (optionally) insurance and enhanced DBS rather than Gas Safe or NICEIC registrations. It repeats weekly or fortnightly, which is what makes customer acquisition cost recoverable. Quality is visible to the customer within hours, so trust is earned quickly or lost quickly, which makes it a good test of the Trusted Service Promise.

Why not a broad marketplace. Checkatrade, Rated People, MyBuilder and Bark are lead-generation businesses for trades, so they compete on lead volume. Taskrabbit, Housekeep and Fantastic Services compete on booking convenience. Nobody should try to win all of that at once with a three-person team.

## 2. Launch segment and offering

Segment: dual-income households and busy professionals in owner-occupied and rented homes in south-west London (initial postcode districts SW4, SW11, SW12, SW15, SW17, SW18, SW19), who want a regular clean and are frustrated by cleaners who change every visit, cancel late or are hard to pay and rebook.

Launch offering, two services only:

1. Regular home cleaning. Hourly, minimum two hours, weekly, fortnightly or one-off, with optional add-ons (inside oven, inside fridge, interior windows, ironing).
2. End-of-tenancy cleaning. Fixed price by property size, with an optional re-clean window if the agent or landlord raises issues.

Gardening, handyman, gas, electrical, plumbing and pest control exist in the catalogue as disabled categories flagged "compliance review required". They cannot be switched on from the admin screen until their verification requirements are defined in the database, which is enforced in code.

## 3. Value proposition

"The same trusted cleaner, every visit, at a price you see before you book."

What is meaningfully different, and how it will be tested rather than asserted:

- Preferred professional. Customers can request the same cleaner on a recurring plan and the system schedules around that person. Test: share of recurring visits served by the preferred cleaner (target 85 per cent or higher).
- Transparent pricing. Itemised quote before payment: labour, add-ons, discounts, fees, final amount and cancellation terms. There are no fees that appear at checkout. Test: checkout abandonment attributed to price surprise (survey question).
- Verification you can read. Each profile shows exactly which documents have been seen and when they expire, never a vague "vetted" label. Test: customer survey on trust against competitors.
- Quality management. Punctuality, cancellations, ratings and complaints are tracked per professional and feed matching priority and suspension rules.
- Fair provider economics. Providers see commission and net earnings per job before accepting. Test: provider retention at 90 days.

## 4. Personas

Priya, 34, product manager in Wandsworth. Works hybrid, two children, no time to manage a cleaner. Wants a fortnightly clean with the same person, pays by card, hates chasing. Success: set up once, no messages needed for six weeks.

Marcus, 41, landlord with two lets in Balham. Needs end-of-tenancy cleans to protect the deposit position and wants an invoice per property. Success: books in under five minutes and gets a re-clean if the inventory check fails.

Grace, 29, tenant moving out of a flat in Clapham. One-off, price sensitive, deadline driven. Success: confirmed slot for the handover day with a clear price.

Elena, 38, self-employed cleaner. Currently relies on word of mouth and Facebook groups, with unreliable payment. Wants steady regular clients near home and quick payment. Success: fills a working week with recurring clients and gets paid within a few days of each job.

Imran, operations lead (admin). Needs to approve providers safely, resolve complaints quickly and see whether each booking made money.

## 5. Competitor differentiation matrix

Assessment is based on public positioning as understood at the time of writing and must be re-checked before it is used in marketing. Ratings: Strong, Partial, Weak, Not offered.

| Capability | Roanwick (target) | Housekeep | Taskrabbit | Checkatrade / Rated People / MyBuilder | Fantastic Services |
| --- | --- | --- | --- | --- | --- |
| Fixed price shown before booking | Strong | Strong | Partial (hourly bids) | Weak (quotes) | Strong |
| Same professional every visit, customer chooses | Strong | Partial | Strong (self-selection) | Not offered | Weak |
| Document-level verification shown on profile | Strong (only if we run the process) | Partial | Partial | Partial | Weak |
| Book and pay in the platform | Strong | Strong | Strong | Weak | Strong |
| Multiple services in one booking | Partial (MVP: shared profile, sequential bookings) | Partial | Partial | Weak | Strong |
| Landlord and agent features | Partial (post-MVP: invoices, multi-property) | Weak | Weak | Weak | Partial |

Honest read: no single feature is unique. The wedge is the combination of preferred-professional continuity, itemised pricing and visible verification for recurring cleaning, which has to be proven by retention data.

## 6. MVP scope

In scope (built): customer, provider and admin applications; postcode availability; two services; itemised quotation; slot search and automatic matching; booking with database-level double-booking prevention; sandbox payments with idempotency and webhooks; cancellation and refund policy engine; provider payouts ledger with hold period; reviews, complaints, refund requests; messaging; favourites and preferred professional; recurring plans; promotions and referrals; provider onboarding with document review; audit log; feature flags and business configuration; financial reporting.

Out of scope for the pilot: native apps (the API and token auth are ready for them), real-time chat transport (polling is used), live KYC vendor integration, multi-city operations, automated payroll or tax reporting, AI features.

Prioritised backlog after MVP: 1. TOTP multi-factor authentication for staff. 2. Live Stripe Connect onboarding and transfers. 3. Landlord and agent accounts with multi-property invoicing. 4. SMS and email provider go-live. 5. Home care plans for maintenance (after trade compliance is defined). 6. Native apps on the same API.

## 7. User journeys and acceptance criteria

Book a regular clean.
- Given a customer enters a covered postcode, when they choose "Regular home cleaning", then they see only slots where at least one eligible professional is free.
- When they choose hours, add-ons and frequency, then the quote lists every line, the total and the cancellation terms before any payment step.
- When they pay successfully, then the booking is confirmed or awaiting acceptance and a notification is recorded.
- If two customers choose the same professional and time, then exactly one booking succeeds and the other receives a clear conflict response.
- If payment fails, then the slot is not confirmed and the customer can retry with a different card without creating a duplicate booking.

Cancel or reschedule.
- Given a confirmed booking, the refund shown before cancelling matches the amount refunded.
- Rescheduling only succeeds if the same professional is free, otherwise matching offers alternatives.

Provider joins and works.
- A provider cannot receive bookings until an administrator has approved them and every required document is approved and unexpired.
- When a document passes its expiry date, the provider stops appearing in availability.
- When a job is completed, a payout record is created with a release date after the configured hold period.

Admin controls.
- Every administrative change to a provider, price, flag or setting writes an audit event with actor, time and before and after values.
- Users without the relevant permission receive a 403 and nothing changes.

## 8. Risk register (summary)

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Provider worker-status challenge (HMRC or tribunal) | Medium | High | Specialist employment-law advice before launch; providers set own availability, can substitute and decline work; do not rely on contract labels alone. Required before pilot. |
| Disintermediation (customers and cleaners go off-platform) | High | High | Continuity features worth paying for, payment protection, payout speed, messaging in-platform, no contact details until booking confirmed. Track repeat bookings leaving the platform through cleaner surveys. |
| Marketing claims not matching operations | Medium | High | Badges are generated only from approved documents. Insurance wording reviewed by a solicitor. |
| Unit economics fail at low density | High | High | Pilot restricted to seven postcode districts; contribution margin reporting per booking and area from day one. |
| Safeguarding or property incident | Low | Very high | Enhanced DBS as an optional trust tier, incident process, insurance review, complaint triage with severity. |
| UK GDPR breach or poor retention | Low | High | Data minimisation, encryption in transit, access control, retention schedule, DPIA before launch, ICO registration. |
| Consumer law (cancellation rights, unfair terms, price transparency) | Medium | Medium | Legal review of terms, 14-day right handled with express waiver at booking, clear pre-contract information. |
| Payment model classified as regulated activity | Medium | High | Use Stripe Connect so Stripe holds funds; confirm structure with Stripe and an adviser before live use. |
| VAT mistakes | Medium | Medium | Accountant review: commission is likely vatable; provider VAT status varies. Prices are configured VAT-exclusive or inclusive explicitly. |

## 9. Decisions requiring founder approval

1. Brand name and domain.
2. Launch postcode districts and whether to start with fewer.
3. Commission rate and customer fee (defaults: 22 per cent commission, no customer fee).
4. Whether enhanced DBS is mandatory for cleaners entering homes or a visible optional tier (default: optional tier, because a mandatory check has cost and eligibility implications that need advice).
5. Cancellation policy tiers (default: free more than 48 hours before, 50 per cent between 24 and 48 hours, none within 24 hours).
6. Payout hold period (default: 3 days after completion).
7. Provider classification model and contract, after legal advice.
