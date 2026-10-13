"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Analytics, Dashboard, StudentRow, User } from "../lib/types";
import { Badge, Button, Empty, Meter, Panel, ago, errText, pct, useToast } from "./ui";

export function Ring({ value, size = 120, label }: { value: number; size?: number; label?: string }) {
  const r = (size - 14) / 2, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, value));
  const tone = v >= 75 ? "var(--ok)" : v >= 45 ? "var(--l5)" : "var(--bad)";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${Math.round(v)} percent`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth={9} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={tone} strokeWidth={9} strokeLinecap="round" strokeDasharray={`${(v / 100) * c} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" className="ring-text">{Math.round(v)}%</text>
      {label && <text x="50%" y={size / 2 + 22} textAnchor="middle" className="atext">{label}</text>}
    </svg>
  );
}

export function Progress({ user, onAsk, onQuiz }: { user: User; onAsk: (text: string, topic: string) => void; onQuiz: (topic: string) => void }) {
  const toast = useToast();
  const [d, setD] = useState<Dashboard | null>(null);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [stats, setStats] = useState<Analytics | null>(null);
  useEffect(() => {
    (async () => {
      try { setD(await api.get<Dashboard>("/api/dashboard")); } catch (e) { toast.push(errText(e), "bad"); }
      if (user.role !== "student") { try { setStudents(await api.get<StudentRow[]>("/api/admin/students")); } catch { /* optional */ } }
      if (user.role === "admin") { try { setStats(await api.get<Analytics>("/api/admin/analytics")); } catch { /* optional */ } }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.role]);
  if (!d) return <div className="page"><div className="skeleton tall" /></div>;
  const attemptedAny = d.attempted > 0;
  return (
    <div className="page stack gap-l">
      <div className="hero-row">
        <Panel className="grow"><div className="row gap-l wrap center-y"><Ring value={d.overall} size={132} label="overall" />
          <div className="stack gap-s"><h2>{attemptedAny ? "Your mastery" : "Start with a quiz"}</h2>
            <p className="dim">{attemptedAny ? `${d.attempted} of ${d.topics.length} topics practised.` : "Take a short quiz or solve a lab and your mastery map fills in here."}</p>
            <div className="row gap-s wrap"><Badge tone={d.streak_days > 0 ? "ok" : "neutral"}>{d.streak_days} day streak</Badge>{d.next_topic && <Badge tone="info">Next: {d.next_topic}</Badge>}</div>
            {d.next_topic && <div className="row gap-s wrap"><Button variant="primary" size="sm" icon="quiz" onClick={() => onQuiz(d.next_topic ?? "")}>Quiz me on {d.next_topic}</Button><Button size="sm" icon="tutor" onClick={() => onAsk(`Explain ${d.next_topic} from the basics`, d.next_topic ?? "")}>Study it with the tutor</Button></div>}
          </div></div></Panel>
      </div>
      <Panel title="Topic mastery" flush>
        <div className="topic-grid">{d.topics.map((t) => (
          <div key={t.topic_id} className="topic-card">
            <div className="row between"><b>{t.name}</b><span className="mono dim">{t.attempts ? `${Math.round(t.mastery)}%` : "new"}</span></div>
            <Meter value={t.attempts ? t.mastery : 0} />
            <div className="row between"><span className="dim small">{t.attempts ? `${t.correct}/${t.attempts} correct` : "not started"}</span>
              <div className="row gap-s"><button type="button" className="link small" onClick={() => onQuiz(t.name)}>Quiz</button><button type="button" className="link small" onClick={() => onAsk(`Explain ${t.name}`, t.name)}>Learn</button></div></div>
          </div>))}</div>
      </Panel>
      <Panel title="Recent activity">
        {d.activity.length === 0 ? <Empty icon="clock" title="Nothing yet">Questions, quizzes and labs will be listed here.</Empty> :
          <ul className="activity">{d.activity.slice(0, 10).map((a, i) => <li key={i}><Badge tone={a.kind === "tutor" ? "info" : a.score >= 60 ? "ok" : "warn"}>{a.kind}</Badge><span>{a.topic}</span><span className="dim">{a.kind === "tutor" ? "" : pct(a.score / 100)}</span><span className="dim small">{ago(a.created_at)}</span></li>)}</ul>}
      </Panel>
      {stats && (
        <Panel title="Platform analytics"><div className="stats">
          {([["Users", stats.users], ["Sources", stats.sources], ["Indexed chunks", stats.rag_chunks], ["Questions", stats.questions], ["Tutor chats", stats.chat_sessions], ["Avg latency", `${stats.avg_latency_ms} ms`], ["Grounded answers", pct(stats.grounded_rate)], ["Helpful / not", `${stats.thumbs_up} / ${stats.thumbs_down}`]] as [string, string | number][]).map(([k, v]) => <div key={k} className="stat"><span className="dim small">{k}</span><b>{v}</b></div>)}
        </div></Panel>
      )}
      {students.length > 0 && (
        <Panel title="Learners" flush><div className="scroll-x"><table className="grid"><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Mean mastery</th></tr></thead>
          <tbody>{students.map((s) => <tr key={s.id}><th>{s.name}</th><td>{s.email}</td><td><Badge>{s.role}</Badge></td><td><div className="row gap-s"><Meter value={s.mastery} /><span className="mono">{s.mastery}%</span></div></td></tr>)}</tbody></table></div></Panel>
      )}
    </div>
  );
}
