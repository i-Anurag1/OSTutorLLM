"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { api, streamChat } from "../lib/api";
import type { ChatMsg, Citation, ConversationSummary, Health, RetrievalMeta, Topic } from "../lib/types";
import { Markdown, laneColor } from "../lib/md";
import { Badge, Button, Drawer, Empty, IconButton, Meter, Segmented, ago, cx, errText, pct, useToast, vars } from "./ui";
import { Icon } from "../lib/icons";

export interface Seed { text: string; topic?: string; nonce: number }
const STARTERS = [
  "What is the convoy effect and how does Round Robin avoid it?", "Explain Belady's anomaly with an example",
  "How does the Banker's algorithm decide a state is safe?", "What happens during a system call?",
  "Compare paging and segmentation", "How does copy-on-write make fork cheap?",
];

export function ConfidenceMeta({ meta }: { meta?: RetrievalMeta }) {
  if (!meta) return null;
  return (
    <div className="stack gap-s">
      <div className="row between"><span className="dim">Evidence coverage</span><b className="mono">{pct(meta.coverage)}</b></div>
      <Meter value={meta.coverage * 100} />
      <div className="row gap-s wrap">
        <Badge tone={meta.mode === "hybrid" ? "ok" : "info"} title="Sparse retrieval is always on; dense vectors join when the embedding model is ready">{meta.mode === "hybrid" ? "Hybrid dense + sparse" : "Sparse (BM25 + TF-IDF)"}</Badge>
        {meta.rerank_used && <Badge tone="ok">Reranked</Badge>}
        {meta.latency_ms.total !== undefined && <Badge>{meta.latency_ms.total} ms</Badge>}
        {meta.expanded_terms.map((t) => <Badge key={t} tone="info" title="Added by glossary query expansion">+ {t}</Badge>)}
      </div>
    </div>
  );
}

export function EvidenceList({ citations, open, setOpen }: { citations: Citation[]; open: number | null; setOpen: (n: number | null) => void }) {
  if (!citations.length) return <Empty icon="book" title="No sources yet">Ask a question and the passages used to answer it will appear here.</Empty>;
  return (
    <div className="stack gap-s">
      {citations.map((c, i) => {
        const n = i + 1;
        const isOpen = open === n;
        return (
          <article key={c.id} className={cx("src", isOpen && "open")} style={vars({ "--lane": laneColor(i) })}>
            <button type="button" className="src-head" onClick={() => setOpen(isOpen ? null : n)} aria-expanded={isOpen}>
              <span className="cite static" style={{ background: laneColor(i) }}>{n}</span>
              <span className="src-title"><b>{c.section || c.title}</b><span className="dim">{c.source}</span></span>
              <span className="mono dim">{c.score.toFixed(2)}</span>
            </button>
            <p className={cx("src-text", !isOpen && "clamp")}>{c.text}</p>
            {isOpen && (
              <div className="row gap-s wrap">
                {Object.entries(c.scores).filter(([, v]) => v !== null).map(([k, v]) => <Badge key={k}>{k} {Number(v).toFixed(2)}</Badge>)}
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

function answerBadges(m: ChatMsg) {
  if (m.streaming) return null;
  return (
    <div className="row gap-s wrap">
      {m.abstained && <Badge tone="warn" title="The retrieved evidence did not cover this question, so the tutor declined to guess">Not in the course material</Badge>}
      {!m.abstained && m.grounded && <Badge tone="ok" title={`Supported sentences: ${pct(m.support?.supported_ratio)}`}>Grounded {pct(m.support?.support_score)}</Badge>}
      {!m.abstained && m.grounded === false && (m.citations?.length ?? 0) > 0 && <Badge tone="warn" title="Some claims could not be matched to the cited source. Open the sources to check.">Check sources</Badge>}
      {m.mode === "extractive" && <Badge tone="info" title="The language model was unreachable, so this answer was assembled from your notes">Extractive answer</Badge>}
      {m.mode === "llm" && m.model && <Badge>{m.model}</Badge>}
    </div>
  );
}

export function Tutor({ topics, seed, health, onNavigate }: { topics: Topic[]; seed: Seed | null; health: Health | null; onNavigate: (p: string) => void }) {
  const toast = useToast();
  const [convs, setConvs] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState<"teach" | "socratic" | "exam">("teach");
  const [difficulty, setDifficulty] = useState("adaptive");
  const [busy, setBusy] = useState(false);
  const [evMsg, setEvMsg] = useState<number | null>(null);
  const [openCite, setOpenCite] = useState<number | null>(null);
  const [sheet, setSheet] = useState<"history" | "evidence" | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  const loadConvs = useCallback(async () => {
    try { setConvs(await api.get<ConversationSummary[]>("/api/tutor/conversations")); } catch { /* history is optional */ }
  }, []);
  useEffect(() => { void loadConvs(); }, [loadConvs]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [msgs]);

  const lastAssistant = [...msgs].map((m, i) => ({ m, i })).filter((x) => x.m.role === "assistant").pop()?.i ?? null;
  const shown = evMsg !== null && msgs[evMsg] ? evMsg : lastAssistant;
  const shownMsg = shown !== null ? msgs[shown] : undefined;

  async function send(text?: string, topicOverride?: string) {
    const q = (text ?? input).trim();
    if (q.length < 2 || busy) return;
    const useTopic = topicOverride !== undefined ? topicOverride : topic;
    setInput("");
    setBusy(true);
    setEvMsg(null);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setMsgs((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "", streaming: true }]);
    const patch = (f: (m: ChatMsg) => ChatMsg) => setMsgs((ms) => ms.map((m, i) => (i === ms.length - 1 ? f(m) : m)));
    try {
      await streamChat({ message: q, topic: useTopic || null, mode, difficulty, conversation_id: activeId }, {
        onMeta: (meta) => { setActiveId(meta.conversation_id); patch((m) => ({ ...m, citations: meta.citations, retrieval: meta.retrieval, abstained: meta.abstain })); },
        onToken: (t) => patch((m) => ({ ...m, content: m.content + t })),
        onReplace: (t) => patch((m) => ({ ...m, content: t })),
        onDone: (d) => {
          patch((m) => ({ ...m, content: d.answer, citations: d.citations, support: d.support, grounded: d.grounded, mode: d.mode, model: d.model,
            latency_ms: d.latency_ms, suggestions: d.suggestions, id: d.message_id, retrieval: d.retrieval, abstained: d.abstained, confidence: d.confidence }));
          setActiveId(d.conversation_id);
          void loadConvs();
        },
      }, ctrl.signal);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") patch((m) => ({ ...m, content: m.content || "(stopped)" }));
      else { toast.push(errText(e), "bad"); setMsgs((ms) => ms.slice(0, -2)); setInput(q); }
    } finally {
      patch((m) => (m.streaming ? { ...m, streaming: false } : m));
      setBusy(false);
      abortRef.current = null;
    }
  }

  useEffect(() => {
    if (!seed) return;
    if (seed.topic !== undefined) setTopic(seed.topic);
    void send(seed.text, seed.topic);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.nonce]);

  async function openConv(id: number) {
    try {
      const c = await api.get<{ id: number; topic: string | null; messages: { id: number; role: "user" | "assistant"; content: string; citations: Citation[]; meta: Record<string, unknown>; feedback: number | null }[] }>(`/api/tutor/conversations/${id}`);
      setActiveId(c.id);
      setTopic(c.topic ?? "");
      setMsgs(c.messages.map((m) => ({ id: m.id, role: m.role, content: m.content, citations: m.citations, feedback: m.feedback,
        grounded: m.meta.grounded as boolean | undefined, mode: m.meta.mode as string | undefined, model: m.meta.model as string | undefined,
        latency_ms: m.meta.latency_ms as number | undefined, suggestions: m.meta.suggestions as string[] | undefined, abstained: m.meta.mode === "abstain" })));
      setSheet(null);
    } catch (e) { toast.push(errText(e), "bad"); }
  }
  function newChat() { abortRef.current?.abort(); setActiveId(null); setMsgs([]); setEvMsg(null); setSheet(null); }
  async function removeConv(id: number) {
    try { await api.del(`/api/tutor/conversations/${id}`); if (id === activeId) newChat(); void loadConvs(); } catch (e) { toast.push(errText(e), "bad"); }
  }
  async function vote(i: number, v: 1 | -1) {
    const m = msgs[i];
    if (!m.id) return;
    try {
      const r = await api.post<{ feedback: number | null }>(`/api/tutor/messages/${m.id}/feedback`, { value: v });
      setMsgs((ms) => ms.map((x, k) => (k === i ? { ...x, feedback: r.feedback } : x)));
    } catch (e) { toast.push(errText(e), "bad"); }
  }
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); toast.push("Copied", "ok"); } catch { toast.push("Copy is not available in this browser", "bad"); }
  }
  function cite(i: number, n: number) { setEvMsg(i); setOpenCite(n); setSheet("evidence"); }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } };
  const llmDown = health && !health.llm.reachable;

  const historyList = (
    <div className="stack gap-s">
      <Button variant="primary" icon="plus" onClick={newChat}>New chat</Button>
      {convs.length === 0 && <p className="dim small">Your conversations will appear here.</p>}
      {convs.map((c) => (
        <div key={c.id} className={cx("conv", c.id === activeId && "on")}>
          <button type="button" className="conv-main" onClick={() => void openConv(c.id)}>
            <b>{c.title}</b><span className="dim small">{c.topic ? c.topic + " · " : ""}{ago(c.updated_at)}</span>
          </button>
          <IconButton icon="trash" label="Delete conversation" onClick={() => void removeConv(c.id)} />
        </div>
      ))}
    </div>
  );
  const evidencePane = (
    <div className="stack">
      <ConfidenceMeta meta={shownMsg?.retrieval} />
      <EvidenceList citations={shownMsg?.citations ?? []} open={openCite} setOpen={setOpenCite} />
    </div>
  );

  return (
    <div className="tutor">
      <aside className="tutor-history only-wide">{historyList}</aside>
      <section className="tutor-main">
        <div className="toolbar">
          <div className="row gap-s">
            <button type="button" className="btn btn-ghost btn-sm only-narrow" onClick={() => setSheet("history")}><Icon name="menu" size={16} />History</button>
            <select value={topic} onChange={(e) => setTopic(e.target.value)} aria-label="Topic">
              <option value="">Any topic</option>
              {topics.map((t) => <option key={t.id} value={t.name}>{t.name}</option>)}
            </select>
            <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} aria-label="Level">
              <option value="adaptive">Adaptive level</option><option value="easy">Beginner</option><option value="medium">Intermediate</option><option value="hard">Advanced</option>
            </select>
          </div>
          <Segmented value={mode} onChange={setMode} label="Tutor mode" options={[{ id: "teach", label: "Teach" }, { id: "socratic", label: "Socratic" }, { id: "exam", label: "Exam" }]} />
        </div>
        {llmDown && (
          <div className="notice notice-warn">
            <Icon name="alert" size={16} />
            <span>The language model is offline, so answers are assembled directly from your notes. Start Ollama (<code>ollama serve</code>) and pull <code>{health?.llm.model}</code> for full explanations.</span>
          </div>
        )}
        {health && health.llm.reachable && health.llm.model_available === false && (
          <div className="notice notice-warn"><Icon name="alert" size={16} /><span>Ollama is running but <code>{health.llm.model}</code> is not installed. Run <code>ollama pull {health.llm.model}</code>.</span></div>
        )}
        <div className="thread" aria-live="polite">
          {msgs.length === 0 ? (
            <div className="hello">
              <h2>What would you like to understand?</h2>
              <p className="dim">Answers come from your course material. Sentences are marked with the source that backs them up; anything the sources do not support is flagged.</p>
              <div className="starters">{STARTERS.map((s) => <button key={s} type="button" className="chip" onClick={() => void send(s)}>{s}</button>)}</div>
            </div>
          ) : msgs.map((m, i) => m.role === "user" ? (
            <div key={i} className="bubble user">{m.content}</div>
          ) : (
            <article key={i} className="answer">
              <header className="row between wrap">
                <div className="row gap-s"><span className="avatar"><Icon name="spark" size={14} /></span><b>OSTutor</b></div>
                {answerBadges(m)}
              </header>
              {m.content ? <Markdown text={m.content} support={m.support} lanes={!m.streaming} onCite={(n) => cite(i, n)} /> : <p className="dim typing">Searching the course material…</p>}
              {m.streaming && m.content && <span className="caret" />}
              {!m.streaming && (
                <footer className="row between wrap">
                  <div className="row gap-s">
                    <IconButton icon="copy" label="Copy answer" onClick={() => void copy(m.content)} />
                    <IconButton icon="up" label="Helpful" active={m.feedback === 1} onClick={() => void vote(i, 1)} />
                    <IconButton icon="down" label="Not helpful" active={m.feedback === -1} onClick={() => void vote(i, -1)} />
                    {(m.citations?.length ?? 0) > 0 && <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setEvMsg(i); setSheet("evidence"); }}><Icon name="book" size={15} />{m.citations?.length} sources</button>}
                  </div>
                  {m.latency_ms ? <span className="mono dim small">{(m.latency_ms / 1000).toFixed(1)} s</span> : null}
                </footer>
              )}
              {!m.streaming && (m.suggestions?.length ?? 0) > 0 && (
                <div className="row gap-s wrap">{m.suggestions?.map((s) => <button key={s} type="button" className="chip" onClick={() => void send(s)}>{s}</button>)}</div>
              )}
            </article>
          ))}
          <div ref={endRef} />
        </div>
        <div className="composer">
          <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} rows={Math.min(5, Math.max(1, input.split("\n").length))}
            placeholder={mode === "socratic" ? "Ask a question, and I will guide you to the answer…" : "Ask about processes, memory, files, scheduling…"} aria-label="Message" />
          {busy ? <Button variant="danger" icon="stop" onClick={() => abortRef.current?.abort()}>Stop</Button> : <Button variant="primary" icon="send" onClick={() => void send()} disabled={input.trim().length < 2}>Ask</Button>}
        </div>
      </section>
      <aside className="tutor-evidence only-wide">
        <h3>Sources</h3>
        {evidencePane}
        <button type="button" className="link" onClick={() => onNavigate("knowledge")}>Open the retrieval lab</button>
      </aside>
      <Drawer open={sheet === "history"} onClose={() => setSheet(null)} title="Conversations">{historyList}</Drawer>
      <Drawer open={sheet === "evidence"} onClose={() => setSheet(null)} title="Sources">{evidencePane}</Drawer>
    </div>
  );
}
