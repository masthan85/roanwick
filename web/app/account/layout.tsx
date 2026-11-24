import { RequireRole } from "@/components/guard";

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return <RequireRole roles={["customer"]}>{children}</RequireRole>;
}
