"use client";
import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { api } from "../lib/api";
import type { Exercise, RunResult, TestResult } from "../lib/types";
import { Badge, Button, Panel, Segmented, cx, errText, useToast } from "./ui";

export function CodeEditor({ value, onChange, onRun }: { value: string; onChange: (v: string) => void; onRun: () => void }) {
  const gutter = useRef<HTMLDivElement | null>(null);
  const lines = Math.max(1, value.split("\n").length);
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); onRun(); return; }
    if (e.key === "Tab") {
      e.preventDefault();
      const el = e.currentTarget;
      const s = el.selectionStart, t = el.selectionEnd;
      onChange(value.slice(0, s) + "    " + value.slice(t));
      requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = s + 4; });
    }
  };
  return (
    <div className="editor">
      <div className="gutter mono" ref={gutter} aria-hidden="true">{Array.from({ length: lines }, (_, i) => <div key={i}>{i + 1}</div>)}</div>
      <textarea className="code mono" spellCheck={false} value={value} onChange={(e) => onChange(e.target.value)} onKeyDown={onKey}
        onScroll={(e) => { if (gutter.current) gutter.current.scrollTop = e.currentTarget.scrollTop; }} aria-label="Code editor" />
    </div>
  );
}

function Output({ r }: { r: RunResult | null }) {
  if (!r) return <p className="dim">Run your code with the button or Ctrl+Enter. Output appears here.</p>;
  return (
    <div className="stack gap-s">
      <div className="row gap-s"><Badge tone={r.ok ? "ok" : "bad"}>{r.timed_out ? "timed out" : r.ok ? "exit 0" : `exit ${r.exit_code}`}</Badge><Badge>{r.duration_ms} ms</Badge></div>
      {r.stdout && <pre className="term">{r.stdout}</pre>}
      {r.stderr && <pre className="term err">{r.stderr}</pre>}
      {!r.stdout && !r.stderr && <p className="dim">The program finished without printing anything.</p>}
    </div>
  );
}

export function Labs() {
  const toast = useToast();
  const [view, setView] = useState<"exercises" | "sandbox">("exercises");
  const [list, setList] = useState<Exercise[]>([]);
  const [sel, setSel] = useState<Exercise | null>(null);
  const [code, setCode] = useState("");
  const [lang, setLang] = useState<"python" | "shell">("python");
  const [sandbox, setSandbox] = useState("# Python sandbox: math, collections, threading, queue, heapq and more\nimport threading\n\ndef worker(n):\n    print('worker', n)\n\nts = [threading.Thread(target=worker, args=(i,)) for i in range(3)]\nfor t in ts: t.start()\nfor t in ts: t.join()\n");
  const [out, setOut] = useState<RunResult | null>(null);
  const [test, setTest] = useState<TestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState(false);
  const [done, setDone] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.get<Exercise[]>("/api/labs/exercises").then((l) => { setList(l); if (l[0]) pick(l[0]); }).catch((e) => toast.push(errText(e), "bad"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  function pick(e: Exercise) { setSel(e); setCode(e.starter); setOut(null); setTest(null); setHint(false); setLang(e.language); }

  const current = view === "exercises" ? code : sandbox;
  const setCurrent = view === "exercises" ? setCode : setSandbox;
  const language = view === "exercises" ? sel?.language ?? "python" : lang;

  async function run() {
    setBusy(true); setTest(null);
    try { setOut(await api.post<RunResult>(language === "python" ? "/api/labs/python" : "/api/labs/shell", language === "python" ? { source: current } : { script: current })); }
    catch (e) { toast.push(errText(e), "bad"); } finally { setBusy(false); }
  }
  async function check() {
    if (!sel) return;
    setBusy(true);
    try {
      const r = await api.post<TestResult>("/api/labs/test", { exercise_id: sel.id, source: code });
      setTest(r);
      if (r.passed) { setDone((d) => new Set(d).add(sel.id)); toast.push("Exercise solved. Mastery updated.", "ok"); }
    } catch (e) { toast.push(errText(e), "bad"); } finally { setBusy(false); }
  }
  const groups = list.reduce<Record<string, Exercise[]>>((a, e) => { (a[e.topic] ||= []).push(e); return a; }, {});

  return (
    <div className="page labs">
      <aside className="labs-list">
        <Segmented value={view} onChange={setView} options={[{ id: "exercises", label: "Exercises" }, { id: "sandbox", label: "Sandbox" }]} />
        {view === "exercises" ? Object.entries(groups).map(([topic, items]) => (
          <div key={topic} className="stack gap-s"><span className="dim small caps">{topic}</span>
            {items.map((e) => <button key={e.id} type="button" className={cx("ex", sel?.id === e.id && "on")} onClick={() => pick(e)}><span>{e.title}</span><span className="row gap-s">{done.has(e.id) && <Badge tone="ok">solved</Badge>}<Badge>{e.language}</Badge></span></button>)}</div>
        )) : (
          <div className="stack gap-s"><Segmented value={lang} onChange={setLang} options={[{ id: "python", label: "Python" }, { id: "shell", label: "Shell" }]} />
            <p className="dim small">{lang === "python" ? "Allowed imports: math, random, collections, itertools, functools, heapq, bisect, re, json, threading, queue, time, dataclasses and a few more. No files, network or eval." : "A restricted bash with ls, cat, grep, wc, sort, uniq, cut, tr, head, tail, seq, expr and more. Pipes, variables, loops and functions work; cd and file redirection do not."}</p></div>
        )}
      </aside>
      <div className="labs-work stack">
        {view === "exercises" && sel && (
          <Panel title={sel.title} actions={<><Badge>{sel.difficulty}</Badge><Badge tone="info">{sel.language}</Badge></>}>
            <p>{sel.prompt}</p>
            <div className="row gap-s wrap"><Button size="sm" variant="ghost" onClick={() => setHint((h) => !h)}>{hint ? "Hide hint" : "Show hint"}</Button><Button size="sm" variant="ghost" onClick={() => { setCode(sel.starter); setTest(null); }}>Reset code</Button></div>
            {hint && <div className="notice notice-info">{sel.hint}</div>}
          </Panel>
        )}
        <Panel title={view === "exercises" ? "Your solution" : `${lang === "python" ? "Python" : "Shell"} sandbox`} actions={<><Button size="sm" icon="play" loading={busy} onClick={() => void run()}>Run</Button>{view === "exercises" && <Button size="sm" variant="primary" icon="check" loading={busy} onClick={() => void check()}>Check</Button>}</>} flush>
          <CodeEditor value={current} onChange={setCurrent} onRun={() => void run()} />
        </Panel>
        {test && (
          <div className={cx("notice", test.passed ? "notice-ok" : "notice-bad")}>
            {test.passed ? <b>All tests passed.</b> : <div className="stack gap-s"><b>Not yet.</b><span>Expected output <code>{test.expected_stdout.trim()}</code>, got <code>{test.actual_stdout.trim() || "(nothing)"}</code>.</span>{test.stderr && <pre className="term err">{test.stderr}</pre>}{test.hint && <span className="dim">Hint: {test.hint}</span>}</div>}
          </div>
        )}
        <Panel title="Output"><Output r={out} /></Panel>
      </div>
    </div>
  );
}
