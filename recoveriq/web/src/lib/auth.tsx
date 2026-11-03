import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, session, type User } from "./api";
import { resetLive } from "./hooks";

type Ctx = {
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
};

const AuthCtx = createContext<Ctx>(null as any);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => session.get()?.user ?? null);
  useEffect(() => {
    const fn = () => setUser(session.get()?.user ?? null);
    window.addEventListener("riq-session", fn);
    return () => window.removeEventListener("riq-session", fn);
  }, []);
  const login = async (email: string, password: string) => {
    const s = await api("/auth/login", { method: "POST", json: { email, password }, auth: false });
    session.set(s);
    resetLive();
    return s.user as User;
  };
  const logout = () => { session.set(null); resetLive(); };
  return <AuthCtx.Provider value={{ user, login, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);

export const can = {
  manage: (u: User | null) => !!u && ["l2", "l1", "exec", "admin"].includes(u.role),
  intake: (u: User | null) => !!u && ["l2", "l1", "admin"].includes(u.role),
  rules: (u: User | null) => !!u && ["l1", "admin"].includes(u.role),
  audit: (u: User | null) => !!u && ["l1", "exec", "admin"].includes(u.role),
  models: (u: User | null) => !!u && ["l1", "exec", "admin"].includes(u.role),
  compliance: (u: User | null) => !!u && ["l1", "exec", "admin"].includes(u.role),
};
