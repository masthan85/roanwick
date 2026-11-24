import type { Metadata } from "next";
import { Container } from "@/components/shell";
import { LinkButton } from "@/components/ui";

export const metadata: Metadata = { title: "How it works", description: "From postcode to paid professional: how booking, payment, cancellation and payouts work on Roanwick." };

export default function HowItWorks() {
  const steps = [
    ["Check your postcode", "We only show services and times where we have approved professionals who cover your area."],
    ["Build your quote", "Choose the length of the visit or the size of your home, add any extras and, if you want, a weekly or fortnightly plan. The quote lists every line and the total."],
    ["Choose a time", "You see times when at least one professional is actually free, including travel time between jobs. You can ask for someone specific if they are available."],
    ["Pay securely", "We hold your slot for 15 minutes while you pay by card. Card details are handled by our payment provider and never stored on our servers."],
    ["The visit", "Your professional can message you through the app. They mark the job started and finished, and you are prompted to review."],
    ["After the visit", "Pay-outs to professionals are released a few days after completion, so that if something went wrong we can step in first."],
  ];
  return (
    <Container narrow className="py-14">
      <h1 className="text-4xl">How it works</h1>
      <ol className="mt-10 space-y-8">
        {steps.map(([t, d], i) => (
          <li key={t} className="flex gap-5">
            <span aria-hidden className="font-display text-3xl text-accent w-8 shrink-0">{i + 1}</span>
            <div><h2 className="text-xl">{t}</h2><p className="mt-1 text-muted">{d}</p></div>
          </li>
        ))}
      </ol>
      <div className="mt-12"><LinkButton href="/book/regular-cleaning">Get a price</LinkButton></div>
    </Container>
  );
}
