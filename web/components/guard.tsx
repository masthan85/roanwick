"use client";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Alert, LinkButton, PageLoading } from "./ui";
import { Container } from "./shell";

export function RequireRole({ roles, children }: { roles: string[]; children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const path = usePathname();
  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(path)}`);
  }, [loading, user, router, path]);
  if (loading || !user) return <PageLoading label="Checking your session" />;
  if (!roles.some((r) => user.roles.includes(r))) {
    return (
      <Container narrow className="py-16">
        <Alert tone="warn" title="This area is not for your account type.">
          <p className="mt-1">You are signed in as {user.email}. Please use the area that matches your account.</p>
        </Alert>
        <div className="mt-4"><LinkButton href="/" variant="secondary">Back to the homepage</LinkButton></div>
      </Container>
    );
  }
  return <>{children}</>;
}
