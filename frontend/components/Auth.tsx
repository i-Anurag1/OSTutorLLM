"use client";
import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "../lib/api";
import type { User } from "../lib/types";
import { Button, Field, errText } from "./ui";
import { Icon } from "../lib/icons";

const DEMOS = [
  { label: "Student", email: "student@ostutor.local", password: "Student123!" },
  { label: "Faculty", email: "faculty@ostutor.local", password: "Faculty123!" },
  { label: "Admin", email: "admin@ostutor.local", password: "Admin123!" },
];

export function Auth({ onAuthed }: { onAuthed: (u: User, token: string) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function go(em: string, pw: string, nm: string, m: "login" | "register") {
    setBusy(true);
    setError("");
    try {
      const r = m === "login"
        ? await api.post<{ access_token: string; user: User }>("/api/auth/login", { email: em, password: pw })
        : await api.post<{ access_token: string; user: User }>("/api/auth/register", { email: em, password: pw, name: nm });
      onAuthed(r.user, r.access_token);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); void go(email, password, name, mode); };

  return (
    <main className="auth">
      <section className="auth-hero">
        <div className="brandmark"><i style={{ width: 34 }} /><i style={{ width: 52, marginLeft: 12 }} /><i style={{ width: 24 }} /></div>
        <h1>OSTutor</h1>
        <p className="lead">An Operating Systems tutor that shows its work. Every answer is built from your course material, and every claim points back to the source that supports it.</p>
        <ul className="auth-points">
          <li><Icon name="shield" size={18} /><span><b>Grounded answers.</b> Citations you can open, with a check on which sentences the evidence really supports.</span></li>
          <li><Icon name="sim" size={18} /><span><b>Step-through simulators.</b> Scheduling, paging, deadlock, disks, philosophers and more.</span></li>
          <li><Icon name="labs" size={18} /><span><b>Safe code labs.</b> Python and shell exercises that grade themselves.</span></li>
        </ul>
      </section>
      <section className="auth-card">
        <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
        <form onSubmit={submit} className="stack">
          {mode === "register" && <Field label="Name"><input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required /></Field>}
          <Field label="Email"><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required /></Field>
          <Field label="Password" hint={mode === "register" ? "At least 8 characters" : undefined}>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 8 : 1} required />
          </Field>
          {error && <div className="notice notice-bad" role="alert">{error}</div>}
          <Button type="submit" variant="primary" loading={busy}>{mode === "login" ? "Sign in" : "Create account"}</Button>
        </form>
        <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
          {mode === "login" ? "New here? Create an account" : "Have an account? Sign in"}
        </button>
        <div className="demo">
          <span className="dim">Try a demo account</span>
          <div className="row gap-s wrap">
            {DEMOS.map((d) => <Button key={d.label} size="sm" variant="soft" disabled={busy} onClick={() => void go(d.email, d.password, "", "login")}>{d.label}</Button>)}
          </div>
        </div>
      </section>
    </main>
  );
}
