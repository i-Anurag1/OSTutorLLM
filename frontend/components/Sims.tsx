"use client";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../lib/api";
import type { BankerResult, CpuCompare, CpuResult, DiningEvent, DiningResult, DiskResult, PageCompare, PageResult, PageStep, PagingResult, PCResult, SegResult, ThreadResult } from "../lib/types";
import { laneColor } from "../lib/md";
import { Badge, Button, Field, Panel, PlayerBar, Segmented, cx, errText, useToast, usePlayer, vars } from "./ui";

const nums = (s: string): number[] => (s.match(/-?\d+/g) ?? []).map(Number);
const rowsOf = (s: string): number[][] => s.split("\n").map(nums).filter((r) => r.length > 0);
const pidColor = (pids: string[], pid: string) => (pid === "IDLE" ? "var(--idle)" : laneColor(pids.indexOf(pid)));

function useRun<T>() {
  const toast = useToast();
  const [data, setData] = useState<T | null>(null);
  const [busy, setBusy] = useState(false);
  async function run(path: string, body: unknown): Promise<T | null> {
    setBusy(true);
    try { const r = await api.post<T>(path, body); setData(r); return r; }
    catch (e) { toast.push(errText(e), "bad"); return null; }
    finally { setBusy(false); }
  }
  return { data, busy, run };
}

function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: "ok" | "warn" | "bad" }) {
  return <div className={cx("stat", tone && `stat-${tone}`)}><span className="dim small">{label}</span><b>{value}</b></div>;
}

export function BarList({ items, unit = "", best }: { items: { label: string; value: number }[]; unit?: string; best?: "min" | "max" }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  const target = best === "min" ? Math.min(...items.map((i) => i.value)) : best === "max" ? max : null;
  return (
    <div className="bars">
      {items.map((it, i) => (
        <div key={it.label} className="bar-row">
          <span className="bar-label">{it.label}</span>
          <div className="bar-track"><i style={vars({ width: `${(it.value / max) * 100}%`, "--lane": laneColor(i) })} className={cx(target !== null && it.value === target && "best")} /></div>
          <b className="mono">{Number.isInteger(it.value) ? it.value : it.value.toFixed(2)}{unit}</b>
        </div>
      ))}
    </div>
  );
}

export function Gantt({ timeline, upto, pids }: { timeline: CpuResult["timeline"]; upto: number; pids: string[] }) {
  const total = Math.max(1, timeline[timeline.length - 1]?.end ?? 1);
  const W = 720, pad = 8, scale = (W - pad * 2) / total;
  const step = total > 60 ? 10 : total > 30 ? 5 : total > 15 ? 2 : 1;
  const ticks: number[] = [];
  for (let t = 0; t <= total; t += step) ticks.push(t);
  return (
    <svg viewBox={`0 0 ${W} 86`} className="chart" role="img" aria-label="Gantt chart of the schedule">
      {timeline.map((s, i) => {
        if (s.start >= upto) return null;
        const w = (Math.min(s.end, upto) - s.start) * scale;
        return (
          <g key={i}>
            <rect x={pad + s.start * scale} y={10} width={Math.max(0, w - 1)} height={40} rx={5} fill={pidColor(pids, s.pid)} opacity={s.pid === "IDLE" ? 0.4 : 1} />
            {w > 24 && <text x={pad + s.start * scale + w / 2} y={35} textAnchor="middle" className="gtext">{s.pid === "IDLE" ? "idle" : s.pid}</text>}
          </g>
        );
      })}
      {ticks.map((t) => (
        <g key={t}><line x1={pad + t * scale} x2={pad + t * scale} y1={54} y2={60} className="axis" /><text x={pad + t * scale} y={76} textAnchor="middle" className="atext">{t}</text></g>
      ))}
      <line x1={pad} x2={W - pad} y1={54} y2={54} className="axis" />
    </svg>
  );
}

export function FrameGrid({ steps, upto, frames }: { steps: PageStep[]; upto: number; frames: number }) {
  return (
    <div className="scroll-x">
      <table className="grid">
        <thead><tr><th>ref</th>{steps.map((s) => <th key={s.index} className={cx(s.index > upto && "future")}>{s.reference}</th>)}</tr></thead>
        <tbody>
          {Array.from({ length: frames }, (_, f) => (
            <tr key={f}>
              <th>F{f + 1}</th>
              {steps.map((s) => (
                <td key={s.index} className={cx(s.index > upto && "future", s.index <= upto && s.fault && s.slot === f && "loaded", s.index === upto && "now")}>
                  {s.index > upto ? "" : s.frames[f] ?? "·"}
                </td>
              ))}
            </tr>
          ))}
          <tr className="result-row">
            <th>·</th>
            {steps.map((s) => <td key={s.index} className={cx(s.index > upto && "future", s.index <= upto && (s.fault ? "bad" : "ok"))}>{s.index > upto ? "" : s.fault ? "F" : "H"}</td>)}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function LineChart({ points, highlight }: { points: { x: number; y: number }[]; highlight?: boolean }) {
  const W = 360, H = 150, p = 28;
  const maxY = Math.max(1, ...points.map((q) => q.y)), maxX = Math.max(1, ...points.map((q) => q.x));
  const X = (x: number) => p + (x / maxX) * (W - p * 2), Y = (y: number) => H - p - (y / maxY) * (H - p * 2);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Page faults against number of frames">
      <polyline points={points.map((q) => `${X(q.x)},${Y(q.y)}`).join(" ")} fill="none" stroke={highlight ? "var(--bad)" : "var(--brand)"} strokeWidth={2.5} />
      {points.map((q) => (<g key={q.x}><circle cx={X(q.x)} cy={Y(q.y)} r={4} fill={highlight ? "var(--bad)" : "var(--brand)"} /><text x={X(q.x)} y={H - 8} textAnchor="middle" className="atext">{q.x}</text><text x={X(q.x)} y={Y(q.y) - 8} textAnchor="middle" className="atext">{q.y}</text></g>))}
      <text x={W / 2} y={12} textAnchor="middle" className="atext">faults vs frames</text>
    </svg>
  );
}

export function DiskChart({ path, size, upto }: { path: number[]; size: number; upto: number }) {
  const W = 720, pad = 20, dy = 26, H = 30 + path.length * dy;
  const X = (c: number) => pad + (c / Math.max(1, size - 1)) * (W - pad * 2);
  const shown = path.slice(0, upto + 1);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Disk head movement">
      {[0, 0.25, 0.5, 0.75, 1].map((f) => (<g key={f}><line x1={X(f * (size - 1))} x2={X(f * (size - 1))} y1={14} y2={H - 6} className="gridline" /><text x={X(f * (size - 1))} y={10} textAnchor="middle" className="atext">{Math.round(f * (size - 1))}</text></g>))}
      <polyline fill="none" stroke="var(--brand)" strokeWidth={2.2} points={shown.map((c, i) => `${X(c)},${24 + i * dy}`).join(" ")} />
      {shown.map((c, i) => (<g key={i}><circle cx={X(c)} cy={24 + i * dy} r={i === 0 ? 6 : 4.5} fill={i === 0 ? "var(--l2)" : "var(--brand)"} /><text x={X(c) + 9} y={28 + i * dy} className="atext">{c}</text></g>))}
    </svg>
  );
}

const STATE_COLOR: Record<string, string> = { thinking: "var(--idle)", hungry: "var(--l5)", holding_first: "var(--l1)", eating: "var(--l3)", done: "var(--line)" };

export function DiningTable({ event, n }: { event: DiningEvent | null; n: number }) {
  const C = 150, R = 105;
  const ang = (i: number) => ((-90 + (i * 360) / n) * Math.PI) / 180;
  const forkAng = (j: number) => ((-90 + ((j + 0.5) * 360) / n) * Math.PI) / 180;
  const states = event?.states ?? Array(n).fill("thinking");
  return (
    <svg viewBox="0 0 300 300" className="chart square" role="img" aria-label="Dining philosophers table">
      <circle cx={C} cy={C} r={78} className="table-disc" />
      {Array.from({ length: n }, (_, j) => {
        const holder = event?.forks[j] ?? null;
        const x = C + 70 * Math.cos(forkAng(j)), y = C + 70 * Math.sin(forkAng(j));
        return <g key={`f${j}`}><circle cx={x} cy={y} r={9} fill={holder === null ? "var(--surface)" : laneColor(holder)} stroke="var(--ink-3)" strokeWidth={1.5} /><text x={x} y={y + 3.5} textAnchor="middle" className="ftext">{j}</text></g>;
      })}
      {Array.from({ length: n }, (_, i) => {
        const x = C + R * Math.cos(ang(i)), y = C + R * Math.sin(ang(i));
        return <g key={`p${i}`}><circle cx={x} cy={y} r={22} fill={STATE_COLOR[states[i]] ?? "var(--idle)"} stroke={laneColor(i)} strokeWidth={3} /><text x={x} y={y + 4} textAnchor="middle" className="ptext">P{i}</text></g>;
      })}
    </svg>
  );
}

const THREAD_CLASS: Record<string, string> = { NEW: "st-new", READY: "st-ready", RUNNING: "st-running", BLOCKED: "st-blocked", TERMINATED: "st-done" };

function SimHead({ title, blurb }: { title: string; blurb: string }) {
  return <div className="sim-head"><h2>{title}</h2><p className="dim">{blurb}</p></div>;
}

/* ================================================================= CPU */
interface Proc { pid: string; arrival: number; burst: number; priority: number }
const DEFAULT_PROCS: Proc[] = [{ pid: "P1", arrival: 0, burst: 5, priority: 2 }, { pid: "P2", arrival: 1, burst: 3, priority: 1 }, { pid: "P3", arrival: 2, burst: 8, priority: 3 }, { pid: "P4", arrival: 3, burst: 6, priority: 2 }];

function CpuSim() {
  const [alg, setAlg] = useState("Round Robin");
  const [quantum, setQuantum] = useState(2);
  const [procs, setProcs] = useState<Proc[]>(DEFAULT_PROCS);
  const r = useRun<CpuResult>();
  const cmp = useRun<CpuCompare>();
  const makespan = r.data?.makespan ?? 1;
  const p = usePlayer(makespan, 220);
  const upto = p.index + 1;
  const run = async () => { await r.run("/api/simulators/cpu", { algorithm: alg, processes: procs, quantum }); };
  useEffect(() => { void run(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  useEffect(() => { if (r.data) p.reset(true); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [r.data]);
  const set = (i: number, k: keyof Proc, v: string) => setProcs((ps) => ps.map((x, j) => (j === i ? { ...x, [k]: k === "pid" ? v : Math.max(0, Number(v) || 0) } : x)));
  const pids = procs.map((x) => x.pid);
  return (
    <>
      <SimHead title="CPU scheduling" blurb="Compare FCFS, SJF, SRTF, Priority (with or without preemption) and Round Robin on the same workload." />
      <Panel title="Workload" actions={<><select value={alg} onChange={(e) => setAlg(e.target.value)} aria-label="Algorithm">{["FCFS", "SJF", "SRTF", "Priority", "Priority-P", "Round Robin"].map((a) => <option key={a}>{a}</option>)}</select>
        {alg === "Round Robin" && <input className="num" type="number" min={1} value={quantum} onChange={(e) => setQuantum(Math.max(1, Number(e.target.value) || 1))} aria-label="Quantum" title="Time quantum" />}
        <Button variant="primary" icon="play" loading={r.busy} onClick={() => void run()}>Run</Button></>}>
        <div className="scroll-x"><table className="grid edit"><thead><tr><th>Process</th><th>Arrival</th><th>Burst</th><th>Priority</th><th /></tr></thead>
          <tbody>{procs.map((x, i) => (
            <tr key={i}><td><input value={x.pid} onChange={(e) => set(i, "pid", e.target.value)} aria-label="pid" /></td>
              {(["arrival", "burst", "priority"] as const).map((k) => <td key={k}><input className="num" type="number" min={0} value={x[k]} onChange={(e) => set(i, k, e.target.value)} aria-label={k} /></td>)}
              <td><Button size="sm" variant="ghost" icon="x" disabled={procs.length <= 1} onClick={() => setProcs((ps) => ps.filter((_, j) => j !== i))}>{""}</Button></td></tr>))}</tbody></table></div>
        <div className="row gap-s"><Button size="sm" icon="plus" disabled={procs.length >= 8} onClick={() => setProcs((ps) => [...ps, { pid: `P${ps.length + 1}`, arrival: 0, burst: 4, priority: 1 }])}>Add process</Button>
          <Button size="sm" variant="ghost" onClick={() => setProcs(DEFAULT_PROCS)}>Reset</Button></div>
      </Panel>
      {r.data && (
        <>
          <Panel title="Timeline" actions={<Badge tone="info">{r.data.algorithm}</Badge>}>
            <Gantt timeline={r.data.timeline} upto={upto} pids={pids} />
            <PlayerBar p={p} label={`t = ${upto} / ${makespan}`} />
          </Panel>
          <div className="stats">
            <Stat label="Avg waiting" value={r.data.avg_waiting.toFixed(2)} /><Stat label="Avg turnaround" value={r.data.avg_turnaround.toFixed(2)} />
            <Stat label="Avg response" value={r.data.avg_response.toFixed(2)} /><Stat label="CPU utilisation" value={`${r.data.cpu_utilization}%`} /><Stat label="Context switches" value={r.data.context_switches} />
          </div>
          <Panel title="Per-process metrics" flush>
            <div className="scroll-x"><table className="grid"><thead><tr><th>Process</th><th>Arrival</th><th>Burst</th><th>Completion</th><th>Turnaround</th><th>Waiting</th><th>Response</th></tr></thead>
              <tbody>{r.data.metrics.map((m) => (<tr key={m.pid}><th><i className="dot" style={{ background: pidColor(pids, m.pid) }} />{m.pid}</th><td>{m.arrival}</td><td>{m.burst}</td><td>{m.completion}</td><td>{m.turnaround}</td><td>{m.waiting}</td><td>{m.response}</td></tr>))}</tbody></table></div>
          </Panel>
        </>
      )}
      <Panel title="Which algorithm wins on this workload?" actions={<Button size="sm" loading={cmp.busy} onClick={() => void cmp.run("/api/simulators/cpu/compare", { processes: procs, quantum })}>Compare all</Button>}>
        {cmp.data ? <><BarList items={cmp.data.rows.map((x) => ({ label: x.algorithm, value: x.avg_waiting }))} best="min" /><p className="dim small">Average waiting time. Lowest: <b>{cmp.data.best_waiting}</b>. Different workloads favour different algorithms - edit the table and compare again.</p></> : <p className="dim">Run every algorithm on the table above and compare average waiting time.</p>}
      </Panel>
    </>
  );
}

/* ================================================================= Page replacement */
function PageSim() {
  const [refs, setRefs] = useState("7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1");
  const [frames, setFrames] = useState(3);
  const [alg, setAlg] = useState("LRU");
  const r = useRun<PageResult>();
  const cmp = useRun<PageCompare>();
  const p = usePlayer(r.data?.steps.length ?? 1, 450);
  const body = () => ({ algorithm: alg, reference_string: nums(refs), frames });
  const run = async () => { await r.run("/api/simulators/page-replacement", body()); await cmp.run("/api/simulators/page-replacement/compare", { reference_string: nums(refs), frames }); };
  useEffect(() => { void run(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  useEffect(() => { if (r.data) p.reset(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [r.data]);
  const cur = r.data?.steps[p.index];
  return (
    <>
      <SimHead title="Page replacement" blurb="Watch frames fill, hit and evict one reference at a time. Try the Belady string to see FIFO get worse with more memory." />
      <Panel title="Input" actions={<Button variant="primary" icon="play" loading={r.busy} onClick={() => void run()}>Run</Button>}>
        <div className="form-grid">
          <Field label="Reference string" className="span2"><input value={refs} onChange={(e) => setRefs(e.target.value)} className="mono" /></Field>
          <Field label="Frames"><input type="number" min={1} max={20} value={frames} onChange={(e) => setFrames(Math.max(1, Math.min(20, Number(e.target.value) || 1)))} /></Field>
          <Field label="Algorithm"><select value={alg} onChange={(e) => setAlg(e.target.value)}>{["FIFO", "LRU", "Optimal", "Clock", "LFU"].map((a) => <option key={a}>{a}</option>)}</select></Field>
        </div>
        <div className="row gap-s wrap"><Button size="sm" onClick={() => { setRefs("7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1"); setFrames(3); }}>Textbook string</Button>
          <Button size="sm" onClick={() => { setRefs("1 2 3 4 1 2 5 1 2 3 4 5"); setFrames(3); setAlg("FIFO"); }}>Belady's anomaly string</Button></div>
      </Panel>
      {r.data && (
        <>
          <Panel title={`${r.data.algorithm} with ${r.data.frames} frames`} actions={<><Badge tone="bad">{r.data.faults} faults</Badge><Badge tone="ok">{r.data.hits} hits</Badge><Badge>{(r.data.fault_rate * 100).toFixed(0)}% fault rate</Badge></>}>
            <FrameGrid steps={r.data.steps} upto={p.index} frames={r.data.frames} />
            <PlayerBar p={p} />
            {cur && <p className="narrate">Reference <b>{cur.reference}</b>: {cur.hit ? "already in memory, so it is a hit." : cur.victim === null ? "not in memory, loaded into a free frame (page fault)." : `not in memory; page ${cur.victim} is evicted and ${cur.reference} loaded (page fault).`}{cur.ref_bits && ` Reference bits: [${cur.ref_bits.join(", ")}].`}</p>}
          </Panel>
        </>
      )}
      {cmp.data && (
        <div className="two">
          <Panel title="Faults by algorithm"><BarList items={cmp.data.rows.map((x) => ({ label: x.algorithm, value: x.faults }))} best="min" /></Panel>
          <Panel title="FIFO faults as frames grow" actions={cmp.data.belady_anomaly ? <Badge tone="bad">Belady's anomaly</Badge> : <Badge tone="ok">No anomaly</Badge>}>
            <LineChart points={cmp.data.belady.map((b) => ({ x: b.frames, y: b.faults }))} highlight={cmp.data.belady_anomaly} />
            <p className="dim small">{cmp.data.belady_anomaly ? "More frames produced MORE faults for this string: the signature of FIFO." : "Faults never increase with memory for this string."}</p>
          </Panel>
        </div>
      )}
    </>
  );
}

/* ================================================================= Disk */
function DiskSim() {
  const [reqs, setReqs] = useState("98 183 37 122 14 124 65 67");
  const [head, setHead] = useState(53);
  const [size, setSize] = useState(200);
  const [alg, setAlg] = useState("SCAN");
  const [dir, setDir] = useState<"up" | "down">("up");
  const r = useRun<DiskResult>();
  const [all, setAll] = useState<{ label: string; value: number }[] | null>(null);
  const p = usePlayer(r.data?.path.length ?? 1, 500);
  const toast = useToast();
  const run = async () => {
    await r.run("/api/simulators/disk", { algorithm: alg, requests: nums(reqs), head, disk_size: size, direction: dir });
    try {
      const rows = await Promise.all(["FCFS", "SSTF", "SCAN", "C-SCAN", "LOOK", "C-LOOK"].map(async (a) => ({ label: a, value: (await api.post<DiskResult>("/api/simulators/disk", { algorithm: a, requests: nums(reqs), head, disk_size: size, direction: dir })).movement })));
      setAll(rows);
    } catch (e) { toast.push(errText(e), "bad"); }
  };
  useEffect(() => { void run(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  useEffect(() => { if (r.data) p.reset(true); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [r.data]);
  return (
    <>
      <SimHead title="Disk scheduling" blurb="Follow the head across cylinders and compare total movement for each policy." />
      <Panel title="Input" actions={<Button variant="primary" icon="play" loading={r.busy} onClick={() => void run()}>Run</Button>}>
        <div className="form-grid">
          <Field label="Request queue" className="span2"><input value={reqs} onChange={(e) => setReqs(e.target.value)} className="mono" /></Field>
          <Field label="Head"><input type="number" min={0} value={head} onChange={(e) => setHead(Number(e.target.value) || 0)} /></Field>
          <Field label="Cylinders"><input type="number" min={2} value={size} onChange={(e) => setSize(Number(e.target.value) || 200)} /></Field>
          <Field label="Algorithm"><select value={alg} onChange={(e) => setAlg(e.target.value)}>{["FCFS", "SSTF", "SCAN", "C-SCAN", "LOOK", "C-LOOK"].map((a) => <option key={a}>{a}</option>)}</select></Field>
          <Field label="Direction"><Segmented value={dir} onChange={setDir} options={[{ id: "up", label: "Up" }, { id: "down", label: "Down" }]} /></Field>
        </div>
      </Panel>
      {r.data && (
        <>
          <Panel title="Head movement" actions={<><Badge tone="info">{r.data.movement} cylinders</Badge><Badge>avg seek {r.data.average_seek}</Badge></>}>
            <DiskChart path={r.data.path} size={r.data.disk_size} upto={p.index} />
            <PlayerBar p={p} label={`move ${p.index} / ${r.data.path.length - 1}`} />
            <p className="dim small">Service order: <span className="mono">{r.data.order.join(" → ")}</span>. Return jumps in C-SCAN and C-LOOK are counted.</p>
          </Panel>
        </>
      )}
      {all && <Panel title="Total head movement by algorithm"><BarList items={all} unit="" best="min" /></Panel>}
    </>
  );
}

/* ================================================================= Banker */
function BankerSim() {
  const [alloc, setAlloc] = useState("0 1 0\n2 0 0\n3 0 2\n2 1 1\n0 0 2");
  const [max, setMax] = useState("7 5 3\n3 2 2\n9 0 2\n2 2 2\n4 3 3");
  const [avail, setAvail] = useState("3 3 2");
  const [reqP, setReqP] = useState(1);
  const [reqV, setReqV] = useState("1 0 2");
  const r = useRun<BankerResult>();
  const base = () => ({ allocation: rowsOf(alloc), maximum: rowsOf(max), available: nums(avail) });
  const run = async (withReq = false) => { await r.run("/api/simulators/banker", withReq ? { ...base(), request: { process: reqP, vector: nums(reqV) } } : base()); };
  useEffect(() => { void run(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  return (
    <>
      <SimHead title="Banker's algorithm" blurb="Check whether a state is safe, see the safe sequence step by step, and test a resource request before granting it." />
      <Panel title="System state" actions={<Button variant="primary" icon="play" loading={r.busy} onClick={() => void run()}>Check safety</Button>}>
        <div className="form-grid three">
          <Field label="Allocation (one row per process)"><textarea rows={6} value={alloc} onChange={(e) => setAlloc(e.target.value)} className="mono" /></Field>
          <Field label="Maximum demand"><textarea rows={6} value={max} onChange={(e) => setMax(e.target.value)} className="mono" /></Field>
          <Field label="Available"><textarea rows={2} value={avail} onChange={(e) => setAvail(e.target.value)} className="mono" /></Field>
        </div>
      </Panel>
      {r.data && (
        <>
          <Panel title="Result" actions={<Badge tone={r.data.safe ? "ok" : "bad"}>{r.data.safe ? "Safe state" : "Unsafe state"}</Badge>}>
            {r.data.safe
              ? <div className="row gap-s wrap"><span className="dim">Safe sequence</span>{r.data.sequence.map((s, i) => <span key={i} className="row gap-s"><span className="pill" style={{ background: laneColor(s) }}>P{s}</span>{i < r.data!.sequence.length - 1 && <span className="dim">→</span>}</span>)}</div>
              : <p>No order lets every process finish with the resources that can become available. The state is <b>unsafe</b> (not necessarily deadlocked, but deadlock is possible).</p>}
            <div className="two"><div><h4>Need = Max − Allocation</h4><table className="grid"><tbody>{r.data.need.map((row, i) => <tr key={i}><th>P{i}</th>{row.map((v, j) => <td key={j}>{v}</td>)}</tr>)}</tbody></table></div>
              <div><h4>Safety trace</h4><ol className="trace">{r.data.steps.map((s, i) => <li key={i}><b>P{s.process}</b> can finish: need [{s.need.join(", ")}] ≤ work [{s.work_before.join(", ")}] → work [{s.work_after.join(", ")}]</li>)}{r.data.steps.length === 0 && <li>No process can start.</li>}</ol></div></div>
          </Panel>
          <Panel title="Request a resource" actions={<Button size="sm" loading={r.busy} onClick={() => void run(true)}>Test request</Button>}>
            <div className="form-grid"><Field label="Process"><input type="number" min={0} value={reqP} onChange={(e) => setReqP(Number(e.target.value) || 0)} /></Field><Field label="Request vector"><input value={reqV} onChange={(e) => setReqV(e.target.value)} className="mono" /></Field></div>
            {r.data.request && <div className={cx("notice", r.data.request.granted ? "notice-ok" : "notice-bad")}><b>{r.data.request.granted ? "Granted. " : "Not granted. "}</b>{r.data.request.reason}.{r.data.request.granted && ` New safe sequence: ${r.data.request.sequence_after.map((x) => "P" + x).join(", ")}.`}</div>}
          </Panel>
        </>
      )}
    </>
  );
}

/* ================================================================= Producer / consumer */
function PCSim() {
  const [size, setSize] = useState(4);
  const [items, setItems] = useState(12);
  const [pp, setPp] = useState(1);
  const [cp, setCp] = useState(3);
  const r = useRun<PCResult>();
  const p = usePlayer(r.data?.events.length ?? 1, 450);
  const run = async () => { await r.run("/api/simulators/producer-consumer", { buffer_size: size, items, producer_period: pp, consumer_period: cp }); };
  useEffect(() => { void run(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  useEffect(() => { if (r.data) p.reset(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [r.data]);
  const ev = r.data?.events[p.index];
  return (
    <>
      <SimHead title="Producer-consumer" blurb="A bounded buffer guarded by the empty, full and mutex semaphores. Make the consumer slower to watch the producer block." />
      <Panel title="Parameters" actions={<Button variant="primary" icon="play" loading={r.busy} onClick={() => void run()}>Run</Button>}>
        <div className="form-grid four">
          <Field label="Buffer size"><input type="number" min={1} max={20} value={size} onChange={(e) => setSize(Math.max(1, Number(e.target.value) || 1))} /></Field>
          <Field label="Items"><input type="number" min={1} max={100} value={items} onChange={(e) => setItems(Math.max(1, Number(e.target.value) || 1))} /></Field>
          <Field label="Producer every N ticks"><input type="number" min={1} max={10} value={pp} onChange={(e) => setPp(Math.max(1, Number(e.target.value) || 1))} /></Field>
          <Field label="Consumer every N ticks"><input type="number" min={1} max={10} value={cp} onChange={(e) => setCp(Math.max(1, Number(e.target.value) || 1))} /></Field>
        </div>
      </Panel>
      {r.data && ev && (
        <>
          <Panel title={`Tick ${ev.tick}`} actions={<><Badge tone="warn">{r.data.producer_blocked} producer waits</Badge><Badge tone="warn">{r.data.consumer_blocked} consumer waits</Badge><Badge>peak {r.data.peak_occupancy}/{r.data.buffer_size}</Badge></>}>
            <div className="buffer">{Array.from({ length: r.data.buffer_size }, (_, i) => <div key={i} className={cx("slot", ev.buffer[i] !== undefined && "full")} style={ev.buffer[i] !== undefined ? vars({ "--lane": laneColor(ev.buffer[i]) }) : undefined}>{ev.buffer[i] ?? ""}</div>)}</div>
            <div className="stats"><Stat label="empty (free slots)" value={ev.empty} /><Stat label="full (items)" value={ev.full} /><Stat label="mutex" value="1" /></div>
            <p className="narrate"><b>{ev.actor}</b>{ev.item !== null ? ` item ${ev.item}` : ""} - {ev.action === "blocked" ? <span className="warn-text">{ev.note}</span> : ev.note}</p>
            <PlayerBar p={p} />
          </Panel>
          <Panel title="Event log" flush>
            <div className="log">{r.data.events.map((e, i) => <button key={i} type="button" className={cx("log-row", i === p.index && "on", e.action === "blocked" && "blocked")} onClick={() => p.setIndex(i)}><span className="mono">t{e.tick}</span><b>{e.actor}</b><span>{e.action}{e.item !== null ? ` #${e.item}` : ""}</span></button>)}</div>
          </Panel>
        </>
      )}
    </>
  );
}

/* ================================================================= Dining philosophers */
function DiningSim() {
  const [strategy, setStrategy] = useState("naive");
  const [n, setN] = useState(5);
  const r = useRun<DiningResult>();
  const p = usePlayer(r.data?.events.length ?? 1, 600);
  const run = async () => { await r.run("/api/simulators/dining-philosophers", { n, strategy, meals: 2 }); };
  useEffect(() => { void run(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  useEffect(() => { if (r.data) p.reset(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [r.data]);
  const ev = r.data?.events[p.index] ?? null;
  return (
    <>
      <SimHead title="Dining philosophers" blurb="Five philosophers, five forks. Compare the naive rule with three deadlock-free strategies." />
      <Panel title="Strategy" actions={<Button variant="primary" icon="play" loading={r.busy} onClick={() => void run()}>Run</Button>}>
        <div className="form-grid">
          <Field label="Rule"><select value={strategy} onChange={(e) => setStrategy(e.target.value)}><option value="naive">Naive: left fork first</option><option value="ordered">Resource ordering</option><option value="asymmetric">Odd/even asymmetric</option><option value="waiter">Waiter (n-1 seats)</option></select></Field>
          <Field label="Philosophers"><input type="number" min={2} max={8} value={n} onChange={(e) => setN(Math.max(2, Math.min(8, Number(e.target.value) || 5)))} /></Field>
        </div>
      </Panel>
      {r.data && (
        <Panel title={r.data.deadlock ? "Deadlock" : "Everyone eats"} actions={<Badge tone={r.data.deadlock ? "bad" : "ok"}>{r.data.deadlock ? `deadlock at step ${r.data.deadlock_at}` : `meals: ${r.data.meals.join(", ")}`}</Badge>}>
          <div className="two center"><DiningTable event={ev} n={r.data.n} />
            <div className="stack"><p>{r.data.explanation}</p>
              <div className="legend">{Object.entries(STATE_COLOR).map(([k, c]) => <span key={k}><i className="dot" style={{ background: c }} />{k.replace("_", " ")}</span>)}</div>
              {ev && <p className={cx("narrate", ev.action === "deadlock" && "warn-text")}>{ev.note}</p>}
              <PlayerBar p={p} /></div></div>
        </Panel>
      )}
    </>
  );
}

/* ================================================================= Paging */
function PagingSim() {
  const [addrs, setAddrs] = useState("10 11 22 35 10 47 12 9 33");
  const [pageSize, setPageSize] = useState(4);
  const [frames, setFrames] = useState(3);
  const [tlb, setTlb] = useState(2);
  const r = useRun<PagingResult>();
  const p = usePlayer(r.data?.rows.length ?? 1, 800);
  const run = async () => { await r.run("/api/simulators/paging", { addresses: nums(addrs), page_size: pageSize, num_frames: frames, tlb_size: tlb }); };
  useEffect(() => { void run(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  useEffect(() => { if (r.data) p.reset(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [r.data]);
  const row = r.data?.rows[p.index];
  return (
    <>
      <SimHead title="Paging and the TLB" blurb="Translate logical addresses through a page table with demand paging, FIFO frame replacement and a small TLB." />
      <Panel title="Input" actions={<Button variant="primary" icon="play" loading={r.busy} onClick={() => void run()}>Translate</Button>}>
        <div className="form-grid four">
          <Field label="Logical addresses" className="span2"><input value={addrs} onChange={(e) => setAddrs(e.target.value)} className="mono" /></Field>
          <Field label="Page size"><input type="number" min={1} value={pageSize} onChange={(e) => setPageSize(Math.max(1, Number(e.target.value) || 1))} /></Field>
          <Field label="Frames"><input type="number" min={1} max={64} value={frames} onChange={(e) => setFrames(Math.max(1, Number(e.target.value) || 1))} /></Field>
          <Field label="TLB entries"><input type="number" min={0} max={16} value={tlb} onChange={(e) => setTlb(Math.max(0, Number(e.target.value) || 0))} /></Field>
        </div>
      </Panel>
      {r.data && row && (
        <>
          <div className="stats"><Stat label="Page faults" value={r.data.faults} tone="bad" /><Stat label="TLB hits" value={r.data.tlb_hits} tone="ok" /><Stat label="TLB hit ratio" value={`${(r.data.tlb_hit_ratio * 100).toFixed(0)}%`} /><Stat label="Offset bits" value={r.data.offset_bits ?? "n/a"} /></div>
          <Panel title={`Address ${row.logical}`}>
            <div className="translate">
              <div><span className="dim small">page = {row.logical} div {pageSize}</span><b>{row.page}</b></div><span>→</span>
              <div><span className="dim small">TLB</span><b className={row.tlb === "hit" ? "ok-text" : "warn-text"}>{row.tlb}</b></div><span>→</span>
              <div><span className="dim small">page table</span><b className={row.fault ? "bad-text" : "ok-text"}>{row.fault ? "fault" : "hit"}</b></div><span>→</span>
              <div><span className="dim small">frame</span><b>{row.frame}</b></div><span>→</span>
              <div><span className="dim small">physical = {row.frame}×{pageSize}+{row.offset}</span><b>{row.physical}</b></div>
            </div>
            {row.victim_page !== null && <p className="narrate">Page {row.victim_page} was evicted (FIFO) to make room.</p>}
            <div className="two"><div><h4>Page table</h4><div className="row gap-s wrap">{Object.entries(row.page_table).map(([k, v]) => <span key={k} className="pill" style={{ background: laneColor(Number(k)) }}>{k}→{v}</span>)}</div></div>
              <div><h4>TLB</h4><div className="row gap-s wrap">{row.tlb_state.length ? row.tlb_state.map((x) => <span key={x} className="pill" style={{ background: laneColor(x) }}>page {x}</span>) : <span className="dim">empty</span>}</div></div></div>
            <PlayerBar p={p} />
          </Panel>
          <Panel title="All translations" flush><div className="scroll-x"><table className="grid"><thead><tr><th>Logical</th><th>Page</th><th>Offset</th><th>TLB</th><th>Fault</th><th>Frame</th><th>Physical</th></tr></thead>
            <tbody>{r.data.rows.map((x, i) => <tr key={i} className={cx(i === p.index && "now")} onClick={() => p.setIndex(i)}><td>{x.logical}</td><td>{x.page}</td><td>{x.offset}</td><td>{x.tlb}</td><td>{x.fault ? "yes" : "no"}</td><td>{x.frame}</td><td>{x.physical}</td></tr>)}</tbody></table></div></Panel>
        </>
      )}
    </>
  );
}

/* ================================================================= Segmentation */
function SegSim() {
  const [segs, setSegs] = useState("1400 1000\n6300 400\n4300 400\n3200 1100\n4700 1000");
  const [logical, setLogical] = useState("2 53\n3 852\n0 1222\n1 399\n7 10");
  const r = useRun<SegResult>();
  const run = async () => { await r.run("/api/simulators/segmentation", { segments: rowsOf(segs).map((x) => ({ base: x[0], limit: x[1] ?? 0 })), logical: rowsOf(logical).map((x) => ({ segment: x[0], offset: x[1] ?? 0 })) }); };
  useEffect(() => { void run(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  return (
    <>
      <SimHead title="Segmentation" blurb="Each logical address is a (segment, offset) pair. The hardware checks the offset against the limit before adding the base." />
      <Panel title="Segment table" actions={<Button variant="primary" icon="play" loading={r.busy} onClick={() => void run()}>Translate</Button>}>
        <div className="form-grid"><Field label="Segments (base limit)"><textarea rows={6} value={segs} onChange={(e) => setSegs(e.target.value)} className="mono" /></Field>
          <Field label="Logical addresses (segment offset)"><textarea rows={6} value={logical} onChange={(e) => setLogical(e.target.value)} className="mono" /></Field></div>
      </Panel>
      {r.data && <Panel title="Translations" flush><div className="scroll-x"><table className="grid"><thead><tr><th>Address</th><th>Base</th><th>Limit</th><th>Physical</th><th>Result</th></tr></thead>
        <tbody>{r.data.rows.map((x, i) => <tr key={i}><th>({x.segment}, {x.offset})</th><td>{x.base ?? "-"}</td><td>{x.limit ?? "-"}</td><td>{x.physical ?? "-"}</td><td><Badge tone={x.valid ? "ok" : "bad"}>{x.reason}</Badge></td></tr>)}</tbody></table></div>
        <p className="dim small pad">{r.data.rule}</p></Panel>}
    </>
  );
}

/* ================================================================= Threads */
function ThreadSim() {
  const [quantum, setQuantum] = useState(2);
  const r = useRun<ThreadResult>();
  const p = usePlayer(r.data?.trace.length ?? 1, 500);
  const run = async () => { await r.run("/api/simulators/threads", { quantum }); };
  useEffect(() => { void run(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  useEffect(() => { if (r.data) p.reset(true); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [r.data]);
  const now = r.data?.trace[p.index];
  return (
    <>
      <SimHead title="Thread life cycle" blurb="Three threads share one CPU. Each alternates CPU and I/O bursts, moving between ready, running, blocked and terminated." />
      <Panel title="Scheduler" actions={<><input className="num" type="number" min={1} max={10} value={quantum} onChange={(e) => setQuantum(Math.max(1, Number(e.target.value) || 1))} aria-label="Quantum" /><Button variant="primary" icon="play" loading={r.busy} onClick={() => void run()}>Run</Button></>}>
        {r.data && (
          <>
            <div className="scroll-x"><table className="grid threads"><tbody>{r.data.threads.map((t) => (
              <tr key={t}><th>Thread {t}</th>{r.data!.trace.slice(0, -1).map((s, i) => <td key={i} className={cx(THREAD_CLASS[s.states[t]], i > p.index && "future", i === p.index && "now")} title={s.states[t]} />)}</tr>))}</tbody></table></div>
            <div className="legend">{r.data.states.map((s) => <span key={s}><i className={cx("dot", THREAD_CLASS[s])} />{s.toLowerCase()}</span>)}</div>
            {now && <p className="narrate">At time {now.t}: {r.data.threads.map((t) => `${t} is ${now.states[t].toLowerCase()}`).join(", ")}.</p>}
            <PlayerBar p={p} label={`t = ${now?.t ?? 0}`} />
          </>
        )}
      </Panel>
    </>
  );
}

/* ================================================================= shell */
const SIMS = [
  { id: "cpu", label: "CPU scheduling", C: CpuSim }, { id: "page", label: "Page replacement", C: PageSim }, { id: "paging", label: "Paging + TLB", C: PagingSim },
  { id: "seg", label: "Segmentation", C: SegSim }, { id: "disk", label: "Disk scheduling", C: DiskSim }, { id: "banker", label: "Banker's algorithm", C: BankerSim },
  { id: "pc", label: "Producer-consumer", C: PCSim }, { id: "dining", label: "Dining philosophers", C: DiningSim }, { id: "threads", label: "Threads", C: ThreadSim },
];
export const SIM_IDS = SIMS.map((s) => ({ id: s.id, label: s.label }));

export function Simulators({ initial }: { initial?: string }) {
  const [id, setId] = useState(initial && SIMS.some((s) => s.id === initial) ? initial : "cpu");
  useEffect(() => { if (initial && SIMS.some((s) => s.id === initial)) setId(initial); }, [initial]);
  const Active = SIMS.find((s) => s.id === id)?.C ?? CpuSim;
  return (
    <div className="page">
      <nav className="simnav" aria-label="Simulators">{SIMS.map((s) => <button key={s.id} type="button" className={cx("simnav-item", s.id === id && "on")} onClick={() => setId(s.id)}>{s.label}</button>)}</nav>
      <div className="stack gap-l" key={id}><Active /></div>
    </div>
  );
}
