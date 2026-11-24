"use client";
import { Container } from "@/components/shell";
import { Button } from "@/components/ui";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <Container narrow className="py-24 text-center">
      <h1 className="text-3xl">Something went wrong</h1>
      <p className="mt-3 text-muted">The page could not be shown. Your booking and payment details have not been affected.</p>
      <div className="mt-6"><Button onClick={reset}>Try again</Button></div>
    </Container>
  );
}
