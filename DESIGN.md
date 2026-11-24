# Roanwick design system

Direction: considered and plain, like a good letter from a local firm. Warm paper, one deep green, a soft editorial serif for headings, and the product itself (real prices, real availability, real verification) as the main imagery instead of stock photography. The site should feel like it belongs to a small, careful business that shows its working.

Basis for this direction: the existing brand (deep green on warm paper, which is kept), the product brief and the rules below. It is not based on a comparison of real sites. The UXKIN tools were not connected when this was written, and no competitor sites were studied for it.

## Colour

Every colour has one job. Light values are the default. Dark values apply under `prefers-color-scheme: dark`. Contrast was computed, not eyeballed.

| Token | Light | Dark | Role | Contrast |
| --- | --- | --- | --- | --- |
| bg | #fbf9f5 | #0d1613 | Page background | n/a |
| surface | #ffffff | #14211d | Cards, inputs, raised panels | n/a |
| sunken | #f4f0e8 | #101b17 | Quiet bands, table headers | n/a |
| ink | #16231f | #e9f1ee | Body text and headings | 15.4:1 and 16.0:1 on bg |
| muted | #55655f | #a3b5ae | Secondary text, hints | 5.9:1 and 8.6:1 on bg; 5.4:1 on sunken |
| line | #e0dacd | #26382f | Borders and dividers | decorative only |
| brand | #1d5c4b | #62c3a0 | Primary buttons, links, active states | 7.4:1 and 8.6:1 on bg |
| brand-hover | #164a3c | #7bd2b2 | Hover on brand | n/a |
| brand-fg | #ffffff | #07130e | Text on a brand fill | 7.8:1 and 8.9:1 |
| brand-soft | #e4efea | #173128 | Selected states, soft highlights | n/a |
| band | #14473a | #0f2a22 | The one full-bleed dark section per page | 10.0:1 for paper text on it |
| accent | #8f5712 | #e3b061 | Small emphasis only: step numbers, a price figure | 5.6:1 and 9.3:1 on bg |
| danger / success / warn | #b3261e / #1b6a38 / #7a4f00 | #ff8d84 / #7fd69b / #f0c35c | State colours, always with words and never alone | 6.2:1, 6.3:1 on bg |

Rules: one primary action colour. Accent never carries meaning that text does not also carry. No gradients as decoration. A flat tint (`brand-soft`) is used instead of the current hero gradient.

## Typography

Two self-hosted variable fonts, so headings look the same on every device. The current stack relies on system serifs (Iowan, Palatino, Georgia), which render as plain Times where they are missing.

| Role | Family | Weights | Notes |
| --- | --- | --- | --- |
| Display and headings | Fraunces Variable | 500, 600 | Soft, warm serif with an optical-size axis. Headings only. |
| Body, UI, numbers | Inter Variable | 400, 500, 600 | Tabular figures on all prices and times. |

Scale (size / line height, in px). Fluid sizes use `clamp` between the mobile and desktop values.

| Step | Mobile | Desktop | Use |
| --- | --- | --- | --- |
| caption | 13 / 18 | 13 / 18 | Legal lines, table captions |
| small | 15 / 22 | 15 / 22 | Hints, metadata |
| body | 17 / 28 | 17 / 28 | All running text. Never below 16. |
| lead | 19 / 30 | 21 / 32 | Intro paragraphs under headings |
| h3 | 22 / 28 | 24 / 30 | Card and item titles |
| h2 | 30 / 36 | 40 / 46 | Section headings |
| h1 | 40 / 44 | 60 / 62 | Hero heading, once per page |
| price | 28 / 32 | 36 / 40 | Totals in quotes (Inter, tabular) |

Line length: 60 to 75 characters for running text (`max-w-prose`, about 68ch). Headings use `text-wrap: balance`.

## Spacing and layout

4px base. Scale: 4, 8, 12, 16, 24, 32, 48, 64, 96, 128. Section padding is 64 on mobile and 96 on desktop. Content width is 1152 for page content and 680 for prose. Gutters are 16 on mobile and 24 from tablet up. Layouts are asymmetric by default (a wide column beside a narrow one). Centred headings are reserved for the hero of the final call to action.

## Shape and depth

| Token | Value | Use |
| --- | --- | --- |
| radius-control | 10px | Buttons, inputs, chips |
| radius-card | 14px | Cards, quote card |
| radius-panel | 24px | Large feature panels |
| radius-pill | 999px | Badges and step pills |
| shadow-raised | 0 1px 2px rgb(22 35 31 / 6%), 0 12px 28px -14px rgb(22 35 31 / 22%) | The hero quote card only |

Borders do the work of depth everywhere else. There are no shadows on ordinary cards.

## Components

Buttons: primary (brand fill, white text), secondary (surface fill, line border), quiet (brand text, no fill). Minimum height 44px, 16px text, weight 500. Hover darkens the fill, focus shows a 3px ring in `ring` with a 2px offset, disabled drops to 50% and shows a not-allowed cursor. One primary button per view.

Links in text are underlined with a 4px offset. Navigation links are not.

Inputs: 44px minimum height, 16px text (prevents zoom on phones), a visible label above, hint below, error in `danger` with an icon-free sentence that says what to do. Never placeholder-only.

Cards: surface fill, 1px line border, 14px radius, 24px padding. No two adjacent sections use the same card pattern.

Signature components, all of which show real data:

- Quote card: itemised lines, tabular figures, the total in the price style, cancellation terms beneath. Figures come from the live API, never typed into the page.
- Availability strip: seven days of real start times.
- Verification profile card: display name, rating if any, and badges that appear only for approved, in-date documents. When shown on marketing pages with sample data it is labelled "Example profile".

Navigation: sticky, 64px, wordmark left, four links, one primary action. Mobile uses a full-width disclosure menu. Footer: four columns and a one-line pilot notice.

## Imagery and icons

No stock photography and no invented people. The product interface is the imagery. Where photography is wanted, it must be real photographs of real professionals or homes, taken with consent and supplied by the business, and the slot is left as a marked placeholder until then. Icons: one set of inline SVGs, 1.75px stroke, 20px, currentColor. The house mark is the only filled glyph. No emoji, and text glyphs such as check marks are replaced with SVG.

## Motion

Transitions only on hover, focus and disclosure, 150ms ease-out. Nothing animates on load. `prefers-reduced-motion` removes all of it (already implemented).

## Voice

Plain British English. Specific nouns and real figures, no superlatives, no claim the operation cannot back. "Checked" means a person reviewed a document. Sample data is always labelled as an example. Prices are written as £66.00, dates as Friday 6 November, times as 10:00.

## Avoid

Gradient text or gradient backgrounds as decoration, glass effects, three identical cards in a row, every section centred, emoji, stock photo smiles, fake reviews, fake logos, made-up counts, and any trust word ("vetted", "insured", "guaranteed") that the process behind it does not support.

## Implementation notes

Where each decision lives in the code, so the file and the app cannot drift apart.

- Colour, radius, shadow and type tokens are CSS variables in `web/app/globals.css`, exposed to Tailwind through `@theme`. Pages use names (`bg-band`, `text-muted`, `rounded-card`, `shadow-raised`) and never raw values. The single hardcoded colour is the browser theme-colour meta tag.
- The type scale is a set of utilities (`text-h1`, `text-h2`, `text-h3`, `text-lead`, `text-price`, `text-small`, `text-caption`) defined in the same file. Body text is 17px. Prices and times use tabular figures.
- Fonts are `@fontsource-variable/fraunces` and `@fontsource-variable/inter`, bundled with the app so they do not depend on a third-party request or on system fonts.
- Icons are in `web/components/icons.tsx`: one set, 20px, 1.75px stroke.
- Landing page sections are in `web/components/home/sections.tsx`. All money, cancellation tiers and district lists come from `web/components/home/data.ts`, which reads the public API, so marketing figures cannot differ from what a quote will say.
- Sample content on marketing pages (the profile card) is labelled "Example profile".
- The page was checked against these rules at 375, 820 and 1280 pixels wide, in light and dark mode, and by keyboard alone. Automated accessibility scans cover the landing page, service page, booking page, login and trust page in dark mode as well as light.

## Open items

Real photography of professionals and homes, supplied with consent, is still wanted for the hero and service pages. Until it exists the design is deliberately photo-free. Testimonials, review counts and visit counts are omitted because none exist yet. Company details and a contact address are placeholders in the footer.
