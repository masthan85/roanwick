import { Container } from "@/components/shell";
import { LinkButton } from "@/components/ui";

export default function NotFound() {
  return (
    <Container narrow className="py-24 text-center">
      <p className="text-muted">Error 404</p>
      <h1 className="text-4xl mt-2">We could not find that page</h1>
      <p className="mt-3 text-muted">The link may be out of date, or the page may have moved.</p>
      <div className="mt-6 flex justify-center gap-3">
        <LinkButton href="/">Go to the homepage</LinkButton>
        <LinkButton href="/help" variant="secondary">Visit the help centre</LinkButton>
      </div>
    </Container>
  );
}
