# Administrator operating guide

This guide is for the people running the pilot day to day. Sign in at `/login` with a staff account. You land on the admin console, and the menu shows only the areas your role allows.

## Roles

| Role | Typical person | Can do |
| --- | --- | --- |
| Operations | Pilot operations lead | Review and approve professionals, assign and manage bookings, handle complaints, manage coverage |
| Support | Customer support | Read bookings, handle complaints and tickets, decide refund requests |
| Finance | Finance or founder | Read bookings, issue refunds, view and manage payouts, see all financial reports, enter costs |
| Super administrator | Founder or technical lead | Everything, including settings, feature flags, staff accounts and the audit log |

Give people the lowest role that lets them do their job. Staff accounts are created under Customers and staff (super administrators only). Every staff member should turn on two-step verification under My security: it adds a 6-digit code from an authenticator app to sign-in. Once everyone has enrolled, a super administrator can switch on the `require_staff_mfa` setting, which blocks anyone without it from admin actions. Keep the number of super administrators small.

## Start of day

Open Overview. The Needs attention panel counts applications waiting for review, paid bookings with no professional, open refund requests, complaints past the response target, professional quality reviews and documents expiring within 30 days. Work through it from the top.

## Approving a professional

1. Open Professionals, filter by status Submitted, and open the application.
2. Read the profile. Check the services and areas make sense.
3. For each document, choose Open file (every view is logged), then Approve or Reject. A rejection needs a note, which is sent to the professional so they can fix it. Check that the name matches the account holder, that the document is in date, and that an insurance certificate names public liability cover and shows a policy number and expiry date. Record the expiry date accurately: the system relies on it.
4. When every mandatory document is approved, choose Approve. The system refuses if anything is missing or expired and tells you what. Only then does the professional appear to customers.
5. Approval, rejection, suspension and every document decision are written to the audit log.

A professional is suspended with a reason. Suspension removes them from search and matching immediately, but their existing bookings need handling: open each one and assign someone else or cancel with a refund.

## Bookings that need a person

A booking appears in Bookings without a professional when its professional declined or withdrew and nobody else was free. Open it, and under Assign a professional pick from the list. The list contains only people who are approved, verified for this service, cover the district and are free at that time. If the list is empty, contact the customer to move the visit, or cancel for the customer, which refunds in full.

## Complaints and refunds

Complaints list shows category, severity and the customer's description. Choose Investigating to acknowledge it (this records the first response time against the target), then Resolved or Not upheld with an outcome the customer will read. A refund can be issued in the same step. Choose who bears the cost: the platform, which reduces our contribution, or the professional, which reduces their payout if it has not been paid yet. If you fund a refund from the professional after their payout was already paid, the amount is recorded as an adjustment, shown at the bottom of the Payouts page, and netted off their next payouts until it is recovered. Use this sparingly and tell the professional first.

Refund requests are a separate queue, filed by customers from their booking. Approve with an amount, or decline, and always give a note.

While a complaint or refund request is open on a booking, the professional's payout for that booking is held automatically.

## Payouts

Payouts are created when a job is completed and are released after the hold period (three days by default). Use Hold to pause one with a reason, and Release to pay it now. In sandbox mode no money moves. In live mode a payout needs the professional's connected payout account.

## Money: how to read the Finance page

Each tile is labelled Actual, Estimate or Manual entry.

Gross booking value is money taken from customers, including credit applied. It is not revenue, because most of it belongs to professionals. Platform revenue is commission plus booking fees less promotions we fund. Contribution is revenue less card processing and platform-funded refunds, and it is before support, marketing and overheads. Processing costs show how much comes from processor data and how much is estimated.

Customer acquisition cost divides marketing spend you enter under Manual costs by new paying customers. Enter marketing spend promptly and use the same channel names that customers arrive with (for example `google_ads`). Without spend entered, the page shows Not available rather than a misleading zero. Lifetime value is an estimate and says what it is based on.

The by-service and by-district tables show where contribution is made or lost. Early numbers are small. Treat any percentage built on fewer than a few dozen bookings as an anecdote.

## Professional quality reviews

The system watches a few signals for each approved professional: withdrawals from confirmed jobs, the share of late starts, the average rating once there are enough reviews, and high-severity complaints. The thresholds are in Settings. When one is crossed, a ticket of type quality review appears in Complaints and refunds, under Tickets, and in Needs attention. It explains why it opened and states that nothing has been changed. Look at the professional's record and decide: coaching, a warning, restricting their areas, or suspension. Reply to the ticket to close it. Only one review ticket is open per professional at a time.

## Changing prices, areas and promotions

Catalogue and promotions lets you change hourly rates, minimum hours, travel gaps, fixed prices by property size and extras. Changes affect new quotes immediately and never alter an existing booking, which keeps its own price lines. Every change records the old and new values in the audit log.

Add a new service with Add a new service at the top of the page. It needs a category, a name, a web address and either an hourly rate or fixed prices by size. A service in a category that is not live stays hidden from customers.

Bundles are packages of extras on one service, such as a move-out pack. A bundle ticks its extras for the customer and takes a percentage off labour and extras. The platform bears the discount and professionals are paid on the full value, so it appears as promotion cost in Finance. Switch a bundle off with its Active box rather than deleting it.

Coverage pauses or adds postcode districts. A paused district stops new bookings and new professional sign-ups there. Existing bookings are not affected.

Promotions create percentage or fixed codes with optional minimum spend, cap, redemption limit, expiry and first-booking-only rules. The platform bears the cost, and the Finance page shows it as promotion cost.

Regulated trades (plumbing, electrical, boiler and heating) cannot be switched on until their document requirements have been defined and you tick the confirmation that someone qualified reviewed them. Do not tick it on your own judgement.

## Settings and feature flags

Settings holds commission, booking fee, cancellation tiers, hold periods and the other commercial assumptions. Rates are in basis points (100 basis points is one per cent) and money is in pence. Values are validated: a commission above 50 per cent is refused. Cancellation tiers are a list, and the last tier must have `hours_before` of 0. Changes apply to new bookings. A booking keeps the cancellation terms it was made under.

Feature flags switch recurring plans, referrals, promotions, choosing a professional and professional sign-ups on or off. Run jobs now executes the maintenance tasks immediately and shows the result.

## Customers

Open Customers and staff and click a name to see an account: sign-in history, bookings, spend, complaints, referral code, credit balance and areas. Suspending an account needs a reason.

## My security

Every signed-in staff member has a My security page for two-step verification. Setup shows a key to enter in an authenticator app, then asks for a code to confirm. If someone loses their device, a super administrator can ask the engineering team to clear their enrolment in the database; there are no recovery codes yet.

## Audit log

Audit log lists who did what and when, with before and after values. Use the filter to find, for example, every `provider` action or every `setting` change.

## Weekly review checklist

Contribution per booking and its trend. Repeat booking rate and 30, 60 and 90 day retention by cohort. Cancellation rate, split by who cancelled. On-time start rate. Complaints per hundred completed visits and any past the response target. Professionals with repeated late starts, withdrawals or low ratings. Documents expiring in the next 30 days. Acquisition by channel against spend. Waiting-list sign-ups by district, which tells you where to expand.
