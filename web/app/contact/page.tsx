"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Container } from "@/components/shell";
import { Alert, Button, ErrorAlert, Field, TextArea, fieldErr, useAsync } from "@/components/ui";

export default function Contact() {
  const [f, setF] = useState({ name: "", email: "", subject: "", message: "" });
  const [done, setDone] = useState<string | null>(null);
  const { loading, error, run } = useAsync();
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <Container narrow className="py-14">
      <h1 className="text-4xl">Contact us</h1>
      <p className="mt-3 text-muted">We aim to reply within one working day. For a problem with a booking, please use Report a problem inside the booking so we can see the details.</p>
      {done ? (
        <Alert tone="success" title="Thank you, we have your message." className="mt-8">Your reference is {done}. We will reply by email.</Alert>
      ) : (
        <form
          className="mt-8 grid gap-5"
          onSubmit={async (e) => {
            e.preventDefault();
            const r = await run(() => api<{ reference: string }>("/contact", { body: f }));
            if (r) setDone(r.reference);
          }}
        >
          <ErrorAlert error={error} />
          <Field label="Your name" value={f.name} onChange={set("name")} required autoComplete="name" error={fieldErr(error, "name")} />
          <Field label="Email address" type="email" value={f.email} onChange={set("email")} required autoComplete="email" error={fieldErr(error, "email")} />
          <Field label="Subject" value={f.subject} onChange={set("subject")} required error={fieldErr(error, "subject")} />
          <TextArea label="Message" value={f.message} onChange={set("message")} required hint="Please do not include card numbers or passwords." error={fieldErr(error, "message")} />
          <Button type="submit" loading={loading} className="justify-self-start">Send message</Button>
        </form>
      )}
    </Container>
  );
}
