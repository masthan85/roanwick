# Compliance and legal register

This is an engineering register, not legal advice. It records what the software does, what it does not do, and where a qualified adviser must decide before the pilot takes real customers or real money. Items marked Required before pilot should block launch.

## Where specialist review is required

| Area | What the software does now | What an adviser must decide | When |
| --- | --- | --- | --- |
| Worker status of professionals | Professionals set their own hours, areas and services and can decline work. Terms say they are in business for themselves, and say we are taking advice. Nothing relies on that label. | Whether the model (control, substitution, exclusivity, pricing set by us, performance management) is genuinely self-employed. Tax and National Minimum Wage exposure. The professional terms and onboarding wording. | Required before pilot |
| Insurance | Public liability certificate is a mandatory document. We record the expiry date, remind the professional, and stop bookings when it lapses. Customer pages say only that a certificate was seen. | Whether to require a minimum cover amount, whether the platform needs its own policy, and the exact customer wording. | Required before pilot |
| Trade qualifications | Regulated categories are switched off. Enabling one needs requirements defined and an explicit confirmation. | Gas Safe, NICEIC or NAPIT, and other registrations; how to verify them; liability. | Before any regulated trade |
| Right to work and identity | A person on our team reviews uploaded documents and records the decision and reviewer. There is no automated identity verification. | Whether manual review is acceptable, the Home Office checking process (share codes), and storage and retention of copies. Whether an identity verification vendor is needed. | Required before pilot |
| DBS | Optional document. A badge appears only if approved. We state that we do not run criminal record checks. | Whether enhanced DBS should be mandatory for work in homes, who is eligible to apply, cost, and the process. | Decision before pilot |
| Consumer cancellation and refund rights | Itemised pre-contract price and cancellation terms, an express request for the service to start during the 14 day period, tiered refunds, full refund where the professional or platform cancels. | Wording of the 14 day cancellation right and the waiver, whether the tiered policy is fair under the Consumer Rights Act 2015, and Digital Markets, Competition and Consumers Act 2024 duties (including price transparency and drip pricing). | Required before pilot |
| VAT and marketplace accounting | Prices have a display flag for VAT. No VAT calculation. Reports use commission as revenue. | Whether we act as principal or agent for VAT, whether commission is vatable, treatment of professionals below the threshold, invoicing, and revenue recognition for credits and promotions. | Required before pilot |
| Payments regulation | Card data never touches our servers. The live design uses Stripe Connect with funds held by Stripe. | Whether holding funds until completion and paying out later falls under payment services regulation for us, and whether a different Connect structure is needed. | Required before live payments |
| Data protection | Data export and account closure endpoints, consent for marketing, audit logging, access control, hashed credentials, document viewing is logged. | Privacy notice, lawful bases, DPIA (identity documents are high risk), retention schedule, ICO registration, processor contracts, international transfers, breach process. | Required before pilot |
| Platform liability | Terms draft says the service contract is between customer and professional. Complaints and refunds are handled. | Allocation of liability for damage and injury, limitation clauses, and what we promise on re-cleans. | Required before pilot |
| Accessibility | Automated WCAG 2.2 AA checks pass on the pages tested. | An independent audit with assistive technology users, and the published accessibility statement. | Before public launch |

## Claims the product makes, and what supports each

| Claim in the product | What supports it |
| --- | --- |
| "Identity document checked", "Right to work checked", "Public liability insurance certificate seen" | Badges derive only from documents a staff member approved and that are in date. |
| "Free cancellation more than 48 hours before" | The tiers are configuration. Text and refund calculations read the same setting. |
| "Payment is protected until the visit is done" | Not stated. The accurate statement is that payouts are held for a few days after completion. |
| "Insured", "guaranteed", "background-checked", "vetted" | Not used anywhere. The trust page says what is and is not checked. |
| Ratings | Shown only from real reviews. Matching treats a professional with fewer than three reviews as neutral rather than using a thin average. |

If the process behind a claim changes, the claim must change with it.

## Data handling

Personal data held: names, email, phone, addresses, access notes, booking history, messages, and for professionals identity, right-to-work and insurance documents. Documents are stored outside the database (local disk in development, object storage in production). They are served only to staff with the `providers.review` permission, with `no-store` caching, and each view is written to the audit log.

Erasure: closing an account anonymises the user row, removes address text, revokes sessions and blocks sign-in. For a professional it also deletes their uploaded documents and removes their profile text. Financial and booking records are retained for statutory periods. The scheduled job purges idempotency records after 7 days and notifications after 180 days. Not yet built: deletion of documents of professionals who simply stop working with us, which needs a retention schedule from the adviser first.

Security controls in place: Argon2id hashing, short-lived access tokens, rotating refresh tokens with reuse detection, lockout, rate limiting on sign-in, registration, quotes and contact, input validation on every route, upload type and size checks with magic-byte verification, security headers, structured logging with request ids, no secrets in the repository (`.env` is ignored; the application refuses to start in production with the development JWT secret), and parameterised queries throughout.

Two-step verification is available to every account and can be made mandatory for staff with a setting. Controls not yet in place: CAPTCHA on public forms, virus scanning of uploads, shared (Redis) rate limiting across processes, encryption of document files at rest in local storage (use S3 server-side encryption in production), field-level encryption, and a penetration test.
