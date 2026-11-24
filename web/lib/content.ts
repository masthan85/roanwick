export interface OfferingContent {
  slug: string;
  category: string;
  name: string;
  tagline: string;
  intro: string;
  included: string[];
  excluded: string[];
  faqs: { q: string; a: string }[];
}

export const OFFERINGS: OfferingContent[] = [
  {
    slug: "regular-cleaning",
    category: "home-cleaning",
    name: "Regular home cleaning",
    tagline: "A clean home on your schedule, from the same professional each visit.",
    intro:
      "Choose how many hours your home needs, pick a day and time, and we match you with an available professional in your area. If you like them, you can ask for them again by name and set up a weekly or fortnightly plan.",
    included: ["Dusting and wiping surfaces", "Vacuuming and mopping floors", "Kitchen worktops, hob and sink", "Bathrooms, toilet and mirrors", "Emptying bins"],
    excluded: ["Inside ovens, fridges and windows unless you add them", "Moving heavy furniture", "Biohazard or hoarding clean-ups", "Anything that needs a ladder"],
    faqs: [
      { q: "How many hours should I book?", a: "As a rough guide, a one-bedroom flat takes two to three hours, a two or three bedroom home three to four. Your professional can tell you after the first visit and you can change the length of later visits." },
      { q: "Do I need to be at home?", a: "No. Many customers leave access instructions in their booking. Your professional will message you through the app if anything is unclear." },
      { q: "Who supplies cleaning products?", a: "Please check with your professional through the booking messages. If you prefer your own products, say so in your booking notes." },
    ],
  },
  {
    slug: "end-of-tenancy-cleaning",
    category: "home-cleaning",
    name: "End of tenancy cleaning",
    tagline: "A checklist-led deep clean for handover day, priced by property size.",
    intro:
      "A fixed price by number of bedrooms, so tenants, landlords and letting agents know the cost in advance. If your agent or landlord raises a cleaning issue within 48 hours of handover, tell us and we will arrange a re-clean of the items raised.",
    included: ["Full kitchen clean including inside the oven", "Bathrooms descaled and sanitised", "Skirting boards, doors and light switches wiped", "Floors vacuumed and mopped", "Inside cupboards and wardrobes wiped"],
    excluded: ["Carpet cleaning unless you add it", "Exterior windows", "Rubbish removal", "Pest or damp treatment"],
    faqs: [
      { q: "Will this guarantee my deposit back?", a: "No cleaning service can promise that. Deposit decisions depend on the inventory, the condition of the property and your tenancy agreement. We will re-clean the items your agent or landlord raises within 48 hours of handover." },
      { q: "Can I book for a landlord or agent?", a: "Yes, you can book on behalf of someone else and enter the property address. Accounts for agents with several properties are on our roadmap." },
    ],
  },
];

export const COMING_LATER = [
  { name: "Handyman", note: "Small repairs and assembly" },
  { name: "Gardening", note: "Lawn care and tidying" },
  { name: "Plumbing", note: "Regulated trade: requirements to be defined" },
  { name: "Electrical", note: "Regulated trade: requirements to be defined" },
  { name: "Boiler and heating", note: "Regulated trade: requirements to be defined" },
];

export const FAQ_GROUPS: { title: string; items: { q: string; a: string }[] }[] = [
  {
    title: "Booking and pricing",
    items: [
      { q: "What will I pay?", a: "Before you pay, we show a line-by-line quote: labour, any extras, plan discounts, any fee and the final total. There are no charges added after that. Our current booking fee is shown on the quote." },
      { q: "When am I charged?", a: "When you confirm your booking. We hold your slot for 15 minutes while you complete payment. Recurring plan visits are charged using the card you saved when you set up the plan." },
      { q: "Can I choose my cleaner?", a: "You can request a specific professional if they are free, or we will match you with the best available person for your postcode and time. After a visit you can save a professional as a favourite and rebook them." },
      { q: "Which areas do you cover?", a: "We are running a pilot in parts of south-west London: SW4, SW11, SW12, SW15, SW17, SW18 and SW19. Enter your postcode on the homepage to check, or join the waiting list." },
    ],
  },
  {
    title: "Changes and cancellations",
    items: [
      { q: "How do I cancel?", a: "Open your booking in your account and choose Cancel. The refund you will receive is shown before you confirm. Our current terms are on the cancellation page." },
      { q: "What if my professional cancels?", a: "You receive a full refund. Where we can, we offer the visit to another available professional first, and tell you if that happens." },
      { q: "Can I move a booking?", a: "Yes, if it is far enough ahead for a full refund under our terms and your professional is free at the new time. Otherwise the cancellation terms apply." },
    ],
  },
  {
    title: "Trust, safety and complaints",
    items: [
      { q: "What do you check?", a: "Before a professional can take bookings, our team reviews their identity document, evidence of their right to work in the UK and their public liability insurance certificate. Each profile shows which of these we have seen and when the insurance expires. We do not claim more than we have checked." },
      { q: "Are professionals employees?", a: "Professionals run their own businesses and choose their own hours, areas and services. We are taking specialist legal advice on how the relationship should be structured." },
      { q: "Something went wrong. What now?", a: "Use Report a problem on your booking. We aim to reply within 48 hours. If we agree the service fell short, we can arrange a re-clean or a refund." },
    ],
  },
  {
    title: "Your data",
    items: [
      { q: "How is my data used?", a: "We use it to run your bookings, take payment and keep everyone safe. We do not sell it. Our privacy notice explains your rights and how to download or delete your data." },
      { q: "Can I delete my account?", a: "Yes. From your profile you can download your data and close your account. We keep financial records for the period the law requires." },
    ],
  },
];
