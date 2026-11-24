"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, refreshSession, setToken } from "./api";

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  roles: string[];
  email_verified: boolean;
  marketing_consent: boolean;
  permissions: string[];
  mfa_enabled: boolean;
}

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, mfaCode?: string) => Promise<User>;
  register: (data: Record<string, unknown>, kind?: "customer" | "provider") => Promise<User>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
  can: (permission: string) => boolean;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      setUser(await api<User>("/auth/me"));
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      if (await refreshSession()) await reload();
      setLoading(false);
    })();
  }, [reload]);

  const value = useMemo<AuthCtx>(
    () => ({
      user,
      loading,
      reload,
      can: (p) => !!user?.permissions.includes(p),
      login: async (email, password, mfaCode) => {
        const r = await api<{ access_token: string; user: User }>("/auth/login", { body: { email, password, mfa_code: mfaCode || null } });
        setToken(r.access_token);
        setUser(r.user);
        return r.user;
      },
      register: async (data, kind = "customer") => {
        const r = await api<{ access_token: string; user: User }>(kind === "provider" ? "/providers/register" : "/auth/register", { body: data });
        setToken(r.access_token);
        setUser(r.user);
        return r.user;
      },
      logout: async () => {
        try {
          await api("/auth/logout", { method: "POST" });
        } finally {
          setToken(null);
          setUser(null);
        }
      },
    }),
    [user, loading, reload],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used inside AuthProvider");
  return c;
}

export const homeFor = (u: User) => (u.roles.some((r) => ["super_admin", "operations", "support", "finance"].includes(r)) ? "/admin" : u.roles.includes("provider") ? "/pro" : "/account");
