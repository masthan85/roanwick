import { RequireRole } from "@/components/guard";

export default function ProLayout({ children }: { children: React.ReactNode }) {
  return <RequireRole roles={["provider"]}>{children}</RequireRole>;
}
