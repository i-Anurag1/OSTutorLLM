"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { QuizQuestion, QuizResult, Topic, VivaResult } from "../lib/types";
import { Badge, Button, Field, Meter, Panel, Segmented, cx, errText, useToast } from "./ui";
import { Ring } from "./Progress";
import { Icon } from "../lib/icons";

const LETTERS = ["A", "B", "C", "D"];

export function Quiz({ topics, initialTopic, onAsk }: { topics: Topic[]; initialTopic?: string; onAsk: (text: string, topic: string) => void }) {
  const toast = useToast();
  const [topic, setTopic] = useState(initialTopic || "");
  const [kind, setKind] = useState<"mcq" | "viva">("mcq");
  const [count, setCount] = useState(5);
  const [qs, setQs] = useState<QuizQuestion[]>([]);
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [vText, setVText] = useState("");
  const [vRes, setVRes] = useState<VivaResult | null>(null);
  const [vScores, setVScores] = useState<number[]>([]);
  const phase = result ? "result" : qs.length ? "run" : "setup";

  useEffect(() => { if (!topic && topics.length) setTopic(initialTopic || topics[0].name); }, [topics, topic, initialTopic]);
  useEffect(() => { if (initialTopic) { setTopic(initialTopic); reset(); } /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [initialTopic]);

  function reset() { setQs([]); setIdx(0); setAnswers({}); setResult(null); setVText(""); setVRes(null); setVScores([]); }
  async function start() {
    setBusy(true);
    try {
      const r = await api.post<{ assessment: QuizQuestion[] }>("/api/quizzes/generate", { topic, kind, count, difficulty: "any" });
      reset();
      setQs(r.assessment);
    } catch (e) { toast.push(errText(e), "bad"); } finally { setBusy(false); }
  }
  async function submit() {
    setBusy(true);
    try {
      const body: Record<string, string> = {};
      for (const q of qs) if (answers[q.id]) body[String(q.id)] = answers[q.id];
      setResult(await api.post<QuizResult>("/api/quizzes/score", { topic, answers: body }));
    } catch (e) { toast.push(errText(e), "bad"); } finally { setBusy(false); }
  }
  async function grade() {
    setBusy(true);
    try {
      const r = await api.post<VivaResult>("/api/quizzes/viva-grade", { question_id: qs[idx].id, answer: vText });
      setVRes(r);
      setVScores((s) => [...s, r.score]);
    } catch (e) { toast.push(errText(e), "bad"); } finally { setBusy(false); }
  }

  const q = qs[idx];
  useEffect(() => {
    if (phase !== "run" || kind !== "mcq") return;
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "TEXTAREA" || t.tagName === "INPUT" || t.tagName === "SELECT") return;
      const i = "abcd".indexOf(e.key.toLowerCase());
      const n = Number(e.key) - 1;
      const pick = i >= 0 ? i : n >= 0 && n < 4 ? n : -1;
      if (pick >= 0 && q?.options?.[pick] !== undefined) setAnswers((a) => ({ ...a, [q.id]: LETTERS[pick] }));
      if (e.key === "ArrowRight") setIdx((x) => Math.min(qs.length - 1, x + 1));
      if (e.key === "ArrowLeft") setIdx((x) => Math.max(0, x - 1));
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [phase, kind, q, qs.length]);

  if (phase === "setup") {
    return (
      <div className="page narrow">
        <Panel title="Practice">
          <div className="stack">
            <Segmented value={kind} onChange={setKind} options={[{ id: "mcq", label: "Multiple choice" }, { id: "viva", label: "Viva (explain in words)" }]} />
            <Field label="Topic"><select value={topic} onChange={(e) => setTopic(e.target.value)}>{topics.map((t) => <option key={t.id} value={t.name}>{t.name}{t.questions ? ` (${t.questions} questions)` : ""}</option>)}</select></Field>
            <Field label="Questions"><select value={count} onChange={(e) => setCount(Number(e.target.value))}>{[3, 5, 8, 10].map((n) => <option key={n} value={n}>{n}</option>)}</select></Field>
            <p className="dim small">{kind === "mcq" ? "Answers are scored on the server, so the correct options are never sent to your browser until you submit." : "Write the answer in your own words. It is graded by how many of the key ideas you covered, then you see the model answer."}</p>
            <Button variant="primary" icon="play" loading={busy} disabled={!topic} onClick={() => void start()}>Start</Button>
          </div>
        </Panel>
      </div>
    );
  }

  if (phase === "result" && result) {
    return (
      <div className="page narrow stack gap-l">
        <Panel>
          <div className="row gap-l wrap center-y"><Ring value={result.score} size={128} />
            <div className="stack gap-s"><h2>{result.correct} of {result.total} correct</h2>
              <p className="dim">{result.recommendation}.{result.mastery !== null && ` Topic mastery is now ${Math.round(result.mastery)}%.`}</p>
              <div className="row gap-s"><Button variant="primary" icon="reset" onClick={() => { reset(); }}>New quiz</Button><Button onClick={() => { setResult(null); setIdx(0); setAnswers({}); }}>Retry these</Button></div></div></div>
        </Panel>
        <Panel title="Review" flush>
          <div className="review">{qs.map((x, i) => {
            const r = result.results.find((y) => y.id === x.id);
            return (
              <article key={x.id} className={cx("review-item", r?.correct ? "good" : "bad")}>
                <div className="row between"><b>{i + 1}. {x.question}</b><Badge tone={r?.correct ? "ok" : "bad"}>{r?.correct ? "Correct" : r?.given ? "Incorrect" : "Skipped"}</Badge></div>
                <ul className="opts">{x.options?.map((o, k) => <li key={k} className={cx(LETTERS[k] === r?.answer && "right", LETTERS[k] === r?.given && LETTERS[k] !== r?.answer && "wrong")}><b>{LETTERS[k]}</b>{o}</li>)}</ul>
                <p className="dim">{r?.explanation}</p>
                {!r?.correct && <button type="button" className="link small" onClick={() => onAsk(`${x.question} Explain why the correct answer is "${x.options?.[LETTERS.indexOf(r?.answer ?? "A")] ?? ""}".`, topic)}>Ask the tutor to explain</button>}
              </article>);
          })}</div>
        </Panel>
      </div>
    );
  }

  if (kind === "viva") {
    const done = vScores.length === qs.length && !!vRes;
    return (
      <div className="page narrow stack gap-l">
        <Panel title={`Viva question ${idx + 1} of ${qs.length}`} actions={<Badge>{topic}</Badge>}>
          <div className="stack"><Meter value={((idx + (vRes ? 1 : 0)) / qs.length) * 100} tone="ok" /><h3 className="q">{q?.question}</h3>
            <textarea rows={5} value={vText} onChange={(e) => setVText(e.target.value)} placeholder="Answer in your own words…" disabled={!!vRes} />
            {!vRes && <Button variant="primary" loading={busy} disabled={vText.trim().length < 3} onClick={() => void grade()}>Grade my answer</Button>}
            {vRes && (
              <div className="stack">
                <div className={cx("notice", vRes.score >= 70 ? "notice-ok" : vRes.score >= 40 ? "notice-warn" : "notice-bad")}><b>{Math.round(vRes.score)}%</b> - {vRes.verdict}</div>
                {vRes.covered_terms.length > 0 && <div className="row gap-s wrap"><span className="dim">Covered</span>{vRes.covered_terms.map((t) => <Badge key={t} tone="ok">{t}</Badge>)}</div>}
                {vRes.missing_terms.length > 0 && <div className="row gap-s wrap"><span className="dim">Missing</span>{vRes.missing_terms.map((t) => <Badge key={t} tone="warn">{t}</Badge>)}</div>}
                <div className="model-answer"><span className="dim small">Model answer</span><p>{vRes.model_answer}</p></div>
                {done ? <div className="row gap-s"><Badge tone="info">Average {Math.round(vScores.reduce((a, b) => a + b, 0) / vScores.length)}%</Badge><Button variant="primary" onClick={reset}>Finish</Button></div>
                  : <Button variant="primary" onClick={() => { setIdx(idx + 1); setVText(""); setVRes(null); }}>Next question</Button>}
              </div>)}
          </div>
        </Panel>
      </div>
    );
  }

  const answered = Object.keys(answers).length;
  return (
    <div className="page narrow stack gap-l">
      <Panel title={`Question ${idx + 1} of ${qs.length}`} actions={<><Badge>{q?.difficulty}</Badge><Badge tone="info">{topic}</Badge></>}>
        <div className="stack"><Meter value={(answered / qs.length) * 100} tone="ok" /><h3 className="q">{q?.question}</h3>
          <div className="options">{q?.options?.map((o, i) => (
            <button key={i} type="button" className={cx("option", answers[q.id] === LETTERS[i] && "on")} onClick={() => setAnswers((a) => ({ ...a, [q.id]: LETTERS[i] }))}><b>{LETTERS[i]}</b><span>{o}</span></button>))}</div>
          <div className="row between"><div className="row gap-s"><Button disabled={idx === 0} onClick={() => setIdx(idx - 1)}>Back</Button><Button disabled={idx === qs.length - 1} onClick={() => setIdx(idx + 1)}>Next</Button></div>
            <Button variant="primary" icon="check" loading={busy} disabled={answered === 0} onClick={() => void submit()}>Submit ({answered}/{qs.length})</Button></div>
          <p className="dim small"><Icon name="info" size={13} /> Tip: press A-D to answer and the arrow keys to move.</p>
        </div>
      </Panel>
    </div>
  );
}
