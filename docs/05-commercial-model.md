# Commercial model and assumptions

Every number here is an assumption chosen to make the unit economics legible. None comes from the Urban Company UK research report (which was not provided) or from market data. All of them live in the database as settings or catalogue rows, so they can be changed from the admin console without a release, and every change is audited.

## Revenue streams

Commission on completed bookings is the primary stream: 22 per cent of service value by default, with an optional per-professional override. A flat customer booking fee exists in the model and is set to zero for the pilot, so that the quote is the simplest it can be. Cancellation charges on late cancellations are treated as service value, and so carry commission. Subscriptions as a paid membership are not included: the recurring plan is a discount on labour, not a fee, until demand is validated.

Bundles (for example the deep-clean refresh: a regular clean with oven, fridge and windows at 10 per cent off) and promotions and referral credit are costs to the platform. Bundle discounts are reported with promotion cost. The professional is always paid on the full service value.

## Launch prices (editable in Catalogue)

| Service | Customer price | Duration |
| --- | --- | --- |
| Regular home cleaning | £22.00 per hour, two hour minimum | Chosen by customer |
| End of tenancy, studio | £150.00 | 4 hours |
| End of tenancy, 1 bedroom | £190.00 | 5 hours |
| End of tenancy, 2 bedrooms | £250.00 | 6 hours |
| End of tenancy, 3 bedrooms | £320.00 | 7 hours |
| End of tenancy, 4 bedrooms | £400.00 | 8 hours |

Extras: inside the oven £25.00, inside the fridge £15.00, interior windows £20.00, ironing £12.00, carpet steam clean £60.00, balcony £20.00. Plan discounts on labour: weekly 10 per cent, fortnightly 5 per cent.

## Worked example: one three-hour clean

| Line | Amount |
| --- | --- |
| Customer pays (3 hours at £22.00) | £66.00 |
| Commission at 22 per cent (platform revenue) | £14.52 |
| Professional receives | £51.48 |
| Card processing, estimated at 1.5% plus 20p | £1.19 |
| Contribution before support and acquisition cost | £13.33 |

If the customer used a 10 per cent first-booking code, the customer pays £59.40, the professional is still paid £51.48, and the platform bears the £6.60 discount: revenue becomes £7.92 and contribution £6.83 (processing fees fall slightly because less cash is taken). A goodwill refund of £10.00 funded by the platform would take contribution negative for that booking, which is why refunds funded by the platform are reported separately.

## What the pilot must show

At £13 of contribution per visit, a customer who books fortnightly for a year (about 26 visits) contributes around £350 before support and overheads. A customer acquisition cost of £40 to £60 would pay back in four to five visits. These are illustrations, not forecasts. The dashboard calculates the real equivalents (contribution per booking, repeat rate, customer acquisition cost from entered marketing spend, and a lifetime value estimate) and labels each as actual, estimated or manual. The lifetime value estimate uses an assumed 14 visits a year until at least 20 customers have a completed booking, and observed data after that.

## Configurable assumptions

| Setting | Default | Meaning |
| --- | --- | --- |
| commission_bps | 2200 | Commission on service value |
| customer_booking_fee_pence | 0 | Flat fee shown in every quote |
| payout_hold_days | 3 | Days between completion and payout |
| cancellation_tiers | 48h 100%, 24h 50%, 0h 0% | Refund by notice |
| hold_minutes | 15 | Slot hold while paying |
| min_notice_hours | 12 | Shortest notice for a new booking |
| booking_horizon_days | 60 | How far ahead customers can book |
| provider_acceptance_hours | 4 | Time to accept before re-matching |
| plan_horizon_days | 8 | How far ahead plan visits are scheduled and charged |
| processing_fee_bps, processing_fee_fixed_pence | 150, 20 | Estimated card fee until processor data is available |
| referral_reward_pence, referral_welcome_pence | 1000, 1000 | Credit for referrer and new customer after first completed visit |
| document_expiry_reminder_days | 30 | When expiry reminders begin |
| complaint_sla_hours | 48 | First-response target |
| quote_valid_minutes | 60 | How long a quotation stays valid |
| assumed_visits_per_year | 14 | Lifetime value assumption |
| require_staff_mfa | off | Block staff without two-step verification from admin actions |
| quality_cancel_threshold | 3 | Withdrawals from confirmed jobs that open a quality review |
| quality_late_rate_pct | 25 | Late-start rate that opens a quality review (after 4 jobs) |
| quality_min_rating | 3.5 | Average rating below which a review opens (after 5 reviews) |

## Payout timing and customer billing

Customers are charged in full when they confirm. Plan visits are scheduled and charged `plan_horizon_days` ahead (about a week), not weeks in advance. The trade-off is that a slot for a plan visit is only reserved once it enters that window, so continuity with the preferred professional is a ranking preference and not a guarantee. If the pilot shows that customers value a reserved slot more than a late charge, the alternative is to reserve visits further ahead and charge a few days before, which needs a pay-later booking state that is not built yet.

Professionals are paid after the hold period unless a complaint or refund request is open on that job. A refund funded by the professional after a payout has already been paid is recorded as an adjustment, shown under Payouts, and netted off their next payouts until recovered. If a professional stops working with us, the balance stays unrecovered, so keep provider-funded refunds for before payout where you can.
