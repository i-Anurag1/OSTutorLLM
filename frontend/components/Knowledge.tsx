"use client";
import { Fragment, useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { api } from "../lib/api";
import type { AnswerEval, EvalAggregate, Hit, RetrievalEval, SearchResult, SourceRow, SystemStatus, User } from "../lib/types";
import { laneColor } from "../lib/md";
import { Badge, Button, Empty, Meter, Panel, Segmented, ago, cx, errText, pct, useToast, vars } from "./ui";
import { ConfidenceMeta } from "./Tutor";
import { Icon } from "../lib/icons";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function HitCard({ h, i }: { h: Hit; i: number }) {
  const [open, setOpen] = useState(false);
  return (
    <article className={cx("src", open && "open")} style={vars({ "--lane": laneColor(i) })}>
      <button type="button" className="src-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="cite static" style={{ background: laneColor(i) }}>{h.rank}</span>
        <span className="src-title"><b>{h.section || h.title}</b><span className="dim">{h.source} · chunk {h.id.split("#")[1]}</span></span>
        <span className="mono dim">{h.score.toFixed(2)}</span>
      </button>
      <div className="row gap-s wrap">{Object.entries(h.scores).filter(([, v]) => v !== null).map(([k, v]) => <Badge key={k} tone={k === "rerank" ? "ok" : "neutral"}>{k} {Number(v).toFixed(3)}</Badge>)}</div>
      <p className={cx("src-text", !open && "clamp")}>{h.text}</p>
    </article>
  );
}

function RetrievalLab({ sources }: { sources: string[] }) {
  const toast = useToast();
  const [q, setQ] = useState("What is the convoy effect?");
  const [k, setK] = useState(6);
  const [src, setSrc] = useState("");
  const [rerank, setRerank] = useState(true);
  const [res, setRes] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  async function go() {
    if (q.trim().length < 2) return;
    setBusy(true);
    try { setRes(await api.post<SearchResult>("/api/rag/search", { query: q, k, source: src || null, use_reranker: rerank })); }
    catch (e) { toast.push(errText(e), "bad"); } finally { setBusy(false); }
  }
  return (
    <div className="stack gap-l">
      <Panel title="See what the tutor sees" actions={<Button variant="primary" icon="search" loading={busy} onClick={() => void go()}>Retrieve</Button>}>
        <div className="stack">
          <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void go(); }} placeholder="Type a question…" aria-label="Query" />
          <div className="row gap-s wrap">
            <select value={k} onChange={(e) => setK(Number(e.target.value))} aria-label="Results">{[3, 6, 10, 15].map((n) => <option key={n} value={n}>{n} results</option>)}</select>
            {sources.length > 0 && <select value={src} onChange={(e) => setSrc(e.target.value)} aria-label="Source"><option value="">All sources</option>{sources.map((s) => <option key={s}>{s}</option>)}</select>}
            <label className="check"><input type="checkbox" checked={rerank} onChange={(e) => setRerank(e.target.checked)} />Cross-encoder rerank</label>
          </div>
          <p className="dim small">Each result shows its score at every stage: BM25 and TF-IDF (sparse), dense similarity, fused RRF rank score and, when available, the reranker. Results are then diversified so the same passage is not repeated.</p>
        </div>
      </Panel>
      {res && (
        <div className="two wide-left">
          <div className="stack">{res.hits.length === 0 ? <Empty icon="search" title="Nothing retrieved">No passage matched these words.</Empty> : res.hits.map((h, i) => <HitCard key={h.id} h={h} i={i} />)}</div>
          <Panel title="Diagnosis"><div className="stack">
            <ConfidenceMeta meta={res.meta} />
            <Badge tone={res.meta.abstain ? "warn" : "ok"} title="The tutor declines to answer when the evidence covers too little of the question">{res.meta.abstain ? "Tutor would decline: not covered by the notes" : "Tutor would answer from these passages"}</Badge>
            <div className="dim small">Candidates searched: {res.meta.candidates}. Stage timings: {Object.entries(res.meta.latency_ms).map(([a, b]) => `${a} ${b} ms`).join(", ")}.</div>
          </div></Panel>
        </div>
      )}
    </div>
  );
}

function Sources() {
  const toast = useToast();
  const [rows, setRows] = useState<SourceRow[]>([]);
  const [banner, setBanner] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const alive = useRef(true);
  const load = async () => { try { setRows(await api.get<SourceRow[]>("/api/sources")); } catch (e) { toast.push(errText(e), "bad"); } };
  useEffect(() => { alive.current = true; void load(); return () => { alive.current = false; }; /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  async function wait(jobId: number | null) {
    setBanner("Indexing in the background…");
    for (let i = 0; i < 90 && alive.current; i++) {
      await sleep(1500);
      try {
        if (jobId) {
          const j = await api.get<{ status: string; error: string }>(`/api/rag/jobs/${jobId}`);
          if (j.status === "completed") { setBanner("Index updated."); break; }
          if (j.status === "failed") { setBanner(`Indexing failed: ${j.error}`); break; }
        } else {
          const s = await api.get<{ indexing: boolean }>("/api/rag/status");
          if (!s.indexing && i > 1) { setBanner("Index updated."); break; }
        }
      } catch { break; }
    }
    if (alive.current) { await load(); setBusy(false); }
  }
  async function upload(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    try { const r = await api.upload<{ job_id: number | null }>("/api/sources/upload", file); toast.push(`${file.name} uploaded`, "ok"); await load(); void wait(r.job_id); }
    catch (e) { toast.push(errText(e), "bad"); setBusy(false); }
  }
  async function rebuild() {
    setBusy(true);
    try { const r = await api.post<{ job_id: number | null }>("/api/rag/rebuild"); void wait(r.job_id); } catch (e) { toast.push(errText(e), "bad"); setBusy(false); }
  }
  async function remove(s: SourceRow) {
    if (!window.confirm(`Remove ${s.name} from the knowledge base?`)) return;
    setBusy(true);
    try { const r = await api.del<{ job_id: number | null }>(`/api/sources/${s.id}`); await load(); void wait(r.job_id); } catch (e) { toast.push(errText(e), "bad"); setBusy(false); }
  }
  const total = rows.reduce((a, r) => a + r.chunks, 0);
  const onDrop = (e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setDrag(false); void upload(e.dataTransfer.files[0]); };
  return (
    <div className="stack gap-l">
      <div className={cx("drop", drag && "on")} onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}>
        <Icon name="upload" size={22} /><b>Drop a PDF, DOCX, PPTX, TXT or Markdown file</b>
        <span className="dim small">Headings become citable sections. Files up to 15 MB are indexed in the background.</span>
        <label className="btn btn-primary btn-sm">Choose file<input type="file" hidden accept=".pdf,.pptx,.docx,.txt,.md" onChange={(e: ChangeEvent<HTMLInputElement>) => { void upload(e.target.files?.[0]); e.target.value = ""; }} /></label>
      </div>
      {banner && <div className="notice notice-info">{busy && <span className="spinner" />}{banner}</div>}
      <Panel title={`${rows.length} sources · ${total} chunks`} actions={<Button size="sm" icon="refresh" loading={busy} onClick={() => void rebuild()}>Rebuild index</Button>} flush>
        {rows.length === 0 ? <Empty icon="file" title="No sources yet">Upload course material to build the knowledge base.</Empty> : (
          <div className="scroll-x"><table className="grid"><thead><tr><th>Name</th><th>Status</th><th>Chunks</th><th>Version</th><th>Added</th><th /></tr></thead>
            <tbody>{rows.map((s) => <tr key={s.id}><th>{s.name}</th><td><Badge tone={s.status === "ready" ? "ok" : s.status === "failed" ? "bad" : "warn"}>{s.status}</Badge></td><td>{s.chunks}</td><td>v{s.version}</td><td className="dim">{ago(s.created_at)}</td><td><Button size="sm" variant="ghost" icon="trash" onClick={() => void remove(s)}>{""}</Button></td></tr>)}</tbody></table></div>)}
      </Panel>
    </div>
  );
}

function AggCards({ agg, order }: { agg: EvalAggregate; order: [string, string][] }) {
  return <div className="stats">{order.map(([k, label]) => <div key={k} className="stat"><span className="dim small">{label}</span><b>{agg[k] === null || agg[k] === undefined ? "-" : Number(agg[k]).toFixed(3)}</b></div>)}</div>;
}

function Evaluation() {
  const toast = useToast();
  const [ret, setRet] = useState<RetrievalEval | null>(null);
  const [ans, setAns] = useState<AnswerEval | null>(null);
  const [busy, setBusy] = useState<"" | "ret" | "ans">("");
  const [n, setN] = useState(8);
  return (
    <div className="stack gap-l">
      <Panel title="Retrieval benchmark" actions={<Button variant="primary" size="sm" icon="play" loading={busy === "ret"} onClick={async () => { setBusy("ret"); try { setRet(await api.post<RetrievalEval>("/api/evaluation/retrieval")); } catch (e) { toast.push(errText(e), "bad"); } finally { setBusy(""); } }}>Run</Button>}>
        <p className="dim small">Does the right source appear in the top results? Fast, needs no language model. The out-of-scope questions test that the tutor declines instead of guessing.</p>
        {ret && (<>
          <AggCards agg={ret.aggregate} order={[["recall_at_k", "Recall@5"], ["mrr", "MRR"], ["ndcg_at_k", "nDCG@5"], ["hit_at_1", "Hit@1"], ["false_abstain_rate", "False abstain"], ["abstention_accuracy", "Abstention accuracy"]]} />
          <p className="dim small">{ret.benchmark_size} questions + {ret.out_of_scope} out-of-scope probes. This benchmark was written alongside the corpus, so treat it as a regression check, not an unseen test.</p>
          <div className="scroll-x"><table className="grid"><thead><tr><th>Question</th><th>Recall</th><th>Hit@1</th><th>Top source</th></tr></thead>
            <tbody>{ret.cases.filter((c) => c.recall_at_k < 1 || c.hit_at_1 < 1).slice(0, 12).map((c) => <tr key={c.id}><th>{c.query}</th><td>{c.recall_at_k}</td><td>{c.hit_at_1}</td><td>{c.top_source}</td></tr>)}{ret.cases.every((c) => c.recall_at_k >= 1 && c.hit_at_1 >= 1) && <tr><td colSpan={4} className="dim">Every question found its source at rank 1.</td></tr>}</tbody></table></div>
        </>)}
      </Panel>
      <Panel title="Answer benchmark" actions={<><select value={n} onChange={(e) => setN(Number(e.target.value))} aria-label="Questions">{[4, 8, 16, 32].map((x) => <option key={x} value={x}>{x} questions</option>)}</select>
        <Button variant="primary" size="sm" icon="play" loading={busy === "ans"} onClick={async () => { setBusy("ans"); try { setAns(await api.post<AnswerEval>(`/api/evaluation/run?limit=${n}`)); } catch (e) { toast.push(errText(e), "bad"); } finally { setBusy(""); } }}>Run</Button></>}>
        <p className="dim small">Generates answers with the configured model and measures citation correctness, groundedness (how much of the answer is supported by its evidence) and concept coverage. Slower: it calls the language model.</p>
        {ans && (<>
          <div className="row gap-s"><Badge tone="info">{ans.model}</Badge><Badge tone={ans.llm_cases === ans.benchmark_size ? "ok" : "warn"}>{ans.llm_cases}/{ans.benchmark_size} answered by the model</Badge></div>
          <AggCards agg={ans.aggregate} order={[["citation_correctness", "Citation correctness"], ["groundedness", "Groundedness"], ["hallucination_rate_proxy", "Hallucination proxy"], ["concept_coverage", "Concept coverage"], ["support_score", "Evidence support"]]} />
          <div className="scroll-x"><table className="grid"><thead><tr><th>Question</th><th>Mode</th><th>Grounded</th><th>Coverage</th></tr></thead>
            <tbody>{ans.cases.map((c) => <tr key={c.id}><th>{c.query}</th><td><Badge tone={c.answer_mode === "llm" ? "ok" : "info"}>{c.answer_mode}</Badge></td><td><div className="row gap-s"><Meter value={c.groundedness * 100} /><span className="mono">{pct(c.groundedness)}</span></div></td><td>{pct(c.concept_coverage)}</td></tr>)}</tbody></table></div>
        </>)}
      </Panel>
    </div>
  );
}

function System() {
  const toast = useToast();
  const [s, setS] = useState<SystemStatus | null>(null);
  useEffect(() => { api.get<SystemStatus>("/api/system/status").then(setS).catch((e) => toast.push(errText(e), "bad")); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  if (!s) return <div className="skeleton tall" />;
  const tuned = s.llm.model.toLowerCase().startsWith("ostutor");
  return (
    <div className="stack gap-l">
      <div className="two">
        <Panel title="Language model" actions={<Badge tone={s.llm.reachable ? (s.llm.model_available === false ? "warn" : "ok") : "bad"}>{s.llm.reachable ? (s.llm.model_available === false ? "model missing" : "ready") : "offline"}</Badge>}>
          <dl className="kv"><dt>Provider</dt><dd>{s.llm.provider}</dd><dt>Model</dt><dd className="mono">{s.llm.model} {tuned && <Badge tone="ok">fine-tuned</Badge>}</dd>{s.llm.error && <><dt>Error</dt><dd className="bad-text">{s.llm.error}</dd></>}</dl>
          {!s.llm.reachable && <div className="notice notice-warn">Start Ollama, then pull the model: <code>ollama pull {s.llm.model}</code>. Until then answers are extractive summaries of your notes.</div>}
          {s.llm.reachable && s.llm.model_available === false && <div className="notice notice-warn">Run <code>ollama pull {s.llm.model}</code> (or import your fine-tuned GGUF with <code>ollama create</code>).</div>}
        </Panel>
        <Panel title="Retrieval" actions={<Badge tone={s.rag.dense_ready ? "ok" : "info"}>{s.rag.dense_ready ? "hybrid" : "sparse"}</Badge>}>
          <dl className="kv"><dt>Chunks</dt><dd>{s.rag.chunks} from {s.rag.sources} sources</dd><dt>Sparse</dt><dd>{s.rag.sparse_retrieval}</dd><dt>Dense</dt><dd>{s.rag.dense_ready ? s.rag.embedding_model : "waiting for the embedding model"}</dd><dt>Vector store</dt><dd>{s.rag.vector_store}</dd><dt>Reranker</dt><dd>{s.rag.reranker_error ? "unavailable" : s.rag.reranker_model}</dd>
            {s.rag.embedding_error && <><dt>Embedding</dt><dd className="warn-text">{s.rag.embedding_error}</dd></>}</dl>
          {s.rag.indexing && <div className="notice notice-info"><span className="spinner" />Indexing…</div>}
        </Panel>
      </div>
      <Panel title="Settings and counts"><dl className="kv wide">{Object.entries(s.settings).map(([k, v]) => <Fragment key={"s" + k}><dt>{k}</dt><dd className="mono">{String(v)}</dd></Fragment>)}{Object.entries(s.counts).map(([k, v]) => <Fragment key={"c" + k}><dt>{k}</dt><dd className="mono">{v}</dd></Fragment>)}</dl><p className="dim small">API version {s.version}</p></Panel>
    </div>
  );
}

export function Knowledge({ user }: { user: User }) {
  const staff = user.role !== "student";
  const [tab, setTab] = useState<"lab" | "sources" | "eval" | "system">("lab");
  const [names, setNames] = useState<string[]>([]);
  useEffect(() => { if (staff) api.get<SourceRow[]>("/api/sources").then((r) => setNames(r.map((x) => x.name))).catch(() => undefined); }, [staff]);
  const tabs = staff ? [{ id: "lab" as const, label: "Retrieval lab" }, { id: "sources" as const, label: "Sources" }, { id: "eval" as const, label: "Evaluation" }, { id: "system" as const, label: "System" }] : [{ id: "lab" as const, label: "Retrieval lab" }];
  return (
    <div className="page stack gap-l">
      {staff && <Segmented value={tab} onChange={setTab} options={tabs} label="Knowledge base" />}
      {tab === "lab" && <RetrievalLab sources={names} />}
      {tab === "sources" && staff && <Sources />}
      {tab === "eval" && staff && <Evaluation />}
      {tab === "system" && staff && <System />}
    </div>
  );
}
