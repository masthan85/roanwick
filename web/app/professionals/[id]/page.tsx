"use client";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { Container } from "@/components/shell";
import { Alert, Card, LinkButton, PageLoading, Stars } from "@/components/ui";

export default function ProProfile() {
  const { id } = useParams<{ id: string }>();
  const { data: p, error } = useSWR(`/professionals/${id}`, fetcher);
  if (error) return <Container narrow className="py-14"><Alert tone="warn" title="This profile is not available.">The professional may no longer be taking bookings.</Alert></Container>;
  if (!p) return <PageLoading />;
  return (
    <Container narrow className="py-12">
      <h1 className="text-4xl">{p.display_name}</h1>
      <div className="mt-2"><Stars value={p.rating_avg} count={p.rating_count} /></div>
      <p className="mt-1 text-muted">{p.jobs_completed} visits completed{p.years_experience ? ` · ${p.years_experience} years of experience` : ""}{p.languages?.length ? ` · ${p.languages.join(", ")}` : ""}</p>
      <p className="mt-6 text-lg">{p.bio}</p>
      <Card className="mt-8">
        <h2 className="text-xl">Checked by Roanwick</h2>
        <p className="text-sm text-muted mt-1">These appear only when our team has reviewed the document and it is still in date.</p>
        <ul className="mt-3 divide-y divide-line">
          {p.badges.length === 0 && <li className="py-2 text-muted">No documents currently on file.</li>}
          {p.badges.map((b: any) => <li key={b.type} className="py-2 flex justify-between gap-3"><span>{b.label}</span><span className="text-muted text-sm">{b.valid_until ? `valid to ${shortDate(b.valid_until)}` : "no expiry"}</span></li>)}
        </ul>
      </Card>
      <h2 className="mt-10 text-2xl">Reviews</h2>
      <div className="mt-4 grid gap-4">
        {p.reviews.length === 0 && <p className="text-muted">No reviews yet.</p>}
        {p.reviews.map((r: any, i: number) => (
          <Card key={i}>
            <Stars value={r.rating} />
            {r.comment && <p className="mt-2">{r.comment}</p>}
            {r.reply && <p className="mt-3 rounded-control bg-sunken p-3 text-small"><strong>Reply from {p.display_name}:</strong> {r.reply}</p>}
            <p className="mt-2 text-xs text-muted">{shortDate(r.at)}</p>
          </Card>
        ))}
      </div>
      <div className="mt-8"><LinkButton href="/book/regular-cleaning">Book a clean</LinkButton></div>
    </Container>
  );
}
