"use client";
import { useCallback, useEffect, useState } from "react";
import { api, setToken } from "../lib/api";
import type { Health, Topic, User } from "../lib/types";
import { Icon } from "../lib/icons";
import type { IconName } from "../lib/icons";
import { Auth } from "../components/Auth";
import { Tutor } from "../components/Tutor";
import type { Seed } from "../components/Tutor";
import { SIM_IDS, Simulators } from "../components/Sims";
import { Quiz } from "../components/Quiz";
import { Labs } from "../components/Labs";
import { Progress } from "../components/Progress";
import { Knowledge } from "../components/Knowledge";
import { Palette } from "../components/Palette";
import type { Command } from "../components/Palette";
import { Badge, IconButton, ToastProvider, cx } from "../components/ui";

type Page = "tutor" | "sims" | "quiz" | "labs" | "progress" | "knowledge";
const NAV: { id: Page; label: string; icon: IconName }[] = [
  { id: "tutor", label: "Tutor", icon: "tutor" }, { id: "sims", label: "Simulators", icon: "sim" }, { id: "quiz", label: "Practice", icon: "quiz" },
  { id: "labs", label: "Code labs", icon: "labs" }, { id: "progress", label: "Progress", icon: "progress" }, { id: "knowledge", label: "Knowledge", icon: "kb" },
];
const isPage = (x: string): x is Page => NAV.some((n) => n.id === x);

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [page, setPage] = useState<Page>("tutor");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [seed, setSeed] = useState<Seed | null>(null);
  const [sim, setSim] = useState<string | undefined>(undefined);
  const [quizTopic, setQuizTopic] = useState<string | undefined>(undefined);
  const [palette, setPalette] = useState(false);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("ostutor.theme");
    setDark(stored ? stored === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches);
    const hash = window.location.hash.replace("#", "");
    if (isPage(hash)) setPage(hash);
    const t = localStorage.getItem("ostutor.token");
    if (!t) { setReady(true); return; }
    setToken(t);
    api.get<User>("/api/auth/me").then(setUser).catch(() => { localStorage.removeItem("ostutor.token"); setToken(""); }).finally(() => setReady(true));
  }, []);

  useEffect(() => { document.documentElement.dataset.theme = dark ? "dark" : "light"; }, [dark]);
  useEffect(() => { if (ready) window.history.replaceState(null, "", "#" + page); }, [page, ready]);

  useEffect(() => {
    if (!user) return;
    api.get<Topic[]>("/api/topics").then(setTopics).catch(() => undefined);
    const poll = () => api.get<Health>("/health").then(setHealth).catch(() => setHealth(null));
    poll();
    const id = setInterval(poll, 20000);
    return () => clearInterval(id);
  }, [user]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); } };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const toggleTheme = () => setDark((d) => { localStorage.setItem("ostutor.theme", d ? "light" : "dark"); return !d; });
  const signIn = (u: User, t: string) => { setToken(t); localStorage.setItem("ostutor.token", t); setUser(u); };
  const signOut = () => { setToken(""); localStorage.removeItem("ostutor.token"); setUser(null); setSeed(null); setHealth(null); };
  const ask = useCallback((text: string, topic?: string) => { setSeed({ text, topic: topic ?? "", nonce: Date.now() }); setPage("tutor"); }, []);
  const openQuiz = (topic: string) => { setQuizTopic(topic); setPage("quiz"); };

  if (!ready) return <div className="splash"><div className="brandmark"><i style={{ width: 34 }} /><i style={{ width: 52, marginLeft: 12 }} /><i style={{ width: 24 }} /></div></div>;
  if (!user) return <Auth onAuthed={signIn} />;

  const commands: Command[] = [
    ...NAV.map((n) => ({ id: "go-" + n.id, label: `Go to ${n.label}`, icon: n.icon, run: () => setPage(n.id) })),
    ...SIM_IDS.map((s) => ({ id: "sim-" + s.id, label: `Open simulator: ${s.label}`, hint: "simulators", icon: "sim" as IconName, run: () => { setSim(s.id); setPage("sims"); } })),
    { id: "theme", label: dark ? "Switch to light theme" : "Switch to dark theme", icon: dark ? "sun" : "moon", run: toggleTheme },
    { id: "out", label: "Sign out", icon: "logout", run: signOut },
  ];
  const llm = health?.llm;
  const llmTone = !health ? "neutral" : !llm?.reachable ? "warn" : llm.model_available === false ? "warn" : "ok";
  const llmText = !health ? "Connecting…" : !llm?.reachable ? "Model offline" : llm.model_available === false ? "Model missing" : "Model ready";
  const ragText = !health ? "" : health.rag.indexing ? "Indexing…" : !health.rag.ready ? "No index" : health.rag.dense_ready ? "Hybrid search" : "Keyword search";
  const title = NAV.find((n) => n.id === page)?.label ?? "";

  return (
    <div className="app">
      <nav className="rail" aria-label="Main">
        <div className="rail-brand"><div className="brandmark small"><i style={{ width: 14 }} /><i style={{ width: 22, marginLeft: 5 }} /><i style={{ width: 10 }} /></div><b>OSTutor</b></div>
        {NAV.map((n) => <button key={n.id} type="button" className={cx("rail-item", page === n.id && "on")} onClick={() => setPage(n.id)} aria-current={page === n.id ? "page" : undefined}><Icon name={n.icon} size={19} /><span>{n.label}</span></button>)}
        <div className="rail-foot">
          <button type="button" className="rail-item" onClick={() => setPalette(true)}><Icon name="command" size={19} /><span>Search</span><kbd>Ctrl K</kbd></button>
        </div>
      </nav>
      <div className="content">
        <header className="topbar">
          <h1>{title}</h1>
          <div className="row gap-s">
            <span className="only-wide row gap-s"><Badge tone={llmTone} title={llm ? `${llm.provider} · ${llm.model}` : ""}>{llmText}</Badge>{ragText && <Badge tone={health?.rag.dense_ready ? "ok" : "info"} title={health ? `${health.rag.chunks} chunks from ${health.rag.sources} sources` : ""}>{ragText}</Badge>}</span>
            <IconButton icon="search" label="Search (Ctrl+K)" onClick={() => setPalette(true)} />
            <IconButton icon={dark ? "sun" : "moon"} label="Toggle theme" onClick={toggleTheme} />
            <span className="user only-wide"><b>{user.name}</b><Badge>{user.role}</Badge></span>
            <IconButton icon="logout" label="Sign out" onClick={signOut} />
          </div>
        </header>
        <main className="main">
          <div hidden={page !== "tutor"} className="fill"><Tutor topics={topics} seed={seed} health={health} onNavigate={(p) => { if (isPage(p)) setPage(p); }} /></div>
          {page === "sims" && <Simulators initial={sim} />}
          {page === "quiz" && <Quiz topics={topics} initialTopic={quizTopic} onAsk={ask} />}
          {page === "labs" && <Labs />}
          {page === "progress" && <Progress user={user} onAsk={ask} onQuiz={openQuiz} />}
          {page === "knowledge" && <Knowledge user={user} />}
        </main>
      </div>
      <nav className="tabbar" aria-label="Main (mobile)">
        {NAV.map((n) => <button key={n.id} type="button" className={cx("tab", page === n.id && "on")} onClick={() => setPage(n.id)}><Icon name={n.icon} size={20} /><span>{n.label}</span></button>)}
      </nav>
      <Palette open={palette} onClose={() => setPalette(false)} commands={commands} onAsk={(q) => ask(q)} />
    </div>
  );
}

export default function Home() {
  return <ToastProvider><App /></ToastProvider>;
}
