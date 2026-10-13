"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { Icon } from "../lib/icons";
import type { IconName } from "../lib/icons";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export const vars = (o: Record<string, string | number>) => o as unknown as CSSProperties;

export function Button({ children, onClick, variant = "soft", size = "md", icon, loading, disabled, type = "button", title, className }: {
  children?: ReactNode; onClick?: () => void; variant?: "primary" | "soft" | "ghost" | "danger"; size?: "sm" | "md"; icon?: IconName;
  loading?: boolean; disabled?: boolean; type?: "button" | "submit"; title?: string; className?: string;
}) {
  return (
    <button type={type} title={title} onClick={onClick} disabled={disabled || loading} className={cx("btn", `btn-${variant}`, size === "sm" && "btn-sm", className)}>
      {loading ? <span className="spinner" /> : icon ? <Icon name={icon} size={size === "sm" ? 15 : 17} /> : null}
      {children}
    </button>
  );
}

export function IconButton({ icon, label, onClick, active }: { icon: IconName; label: string; onClick?: () => void; active?: boolean }) {
  return (
    <button type="button" className={cx("icon-btn", active && "on")} onClick={onClick} aria-label={label} title={label}>
      <Icon name={icon} size={17} />
    </button>
  );
}

export function Panel({ title, actions, children, className, flush }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; flush?: boolean }) {
  return (
    <section className={cx("panel", className)}>
      {(title || actions) && (
        <header className="panel-head">
          <h3>{title}</h3>
          <div className="row gap-s">{actions}</div>
        </header>
      )}
      <div className={flush ? "" : "panel-body"}>{children}</div>
    </section>
  );
}

export function Field({ label, hint, children, className }: { label: string; hint?: string; children: ReactNode; className?: string }) {
  return (
    <label className={cx("field", className)}>
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function Badge({ tone = "neutral", children, title }: { tone?: "ok" | "warn" | "bad" | "info" | "neutral"; children: ReactNode; title?: string }) {
  return <span className={cx("badge", `badge-${tone}`)} title={title}>{children}</span>;
}

export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { id: T; label: string }[]; onChange: (v: T) => void; label?: string }) {
  return (
    <div className="seg" role="tablist" aria-label={label}>
      {options.map((o) => (
        <button key={o.id} type="button" role="tab" aria-selected={o.id === value} className={cx("seg-item", o.id === value && "on")} onClick={() => onChange(o.id)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Meter({ value, tone }: { value: number; tone?: "ok" | "warn" | "bad" }) {
  const t = tone ?? (value >= 75 ? "ok" : value >= 45 ? "warn" : "bad");
  return (
    <div className="meter" role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
      <i className={`meter-${t}`} style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
    </div>
  );
}

export function Empty({ icon, title, children }: { icon: IconName; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon"><Icon name={icon} size={22} /></div>
      <h4>{title}</h4>
      {children && <p>{children}</p>}
    </div>
  );
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="drawer-wrap" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Details">
        <header className="panel-head"><h3>{title}</h3><IconButton icon="x" label="Close" onClick={onClose} /></header>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}

/* ---------------------------------------------------------------- toasts */
interface Toast { id: number; tone: "ok" | "bad" | "info"; text: string }
const ToastCtx = createContext<{ push: (text: string, tone?: Toast["tone"]) => void }>({ push: () => undefined });
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x.slice(-3), { id, tone, text }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), tone === "bad" ? 7000 : 3500);
  }, []);
  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => <div key={t.id} className={cx("toast", `toast-${t.tone}`)}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------------------------------------------------------------- step player for simulators */
export function usePlayer(count: number, ms = 650) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setIndex((i) => {
      if (i >= count - 1) { setPlaying(false); return i; }
      return i + 1;
    }), ms / speed);
    return () => clearInterval(id);
  }, [playing, count, ms, speed]);
  const reset = useCallback((toEnd = false) => { setPlaying(false); setIndex(toEnd ? Math.max(0, count - 1) : 0); }, [count]);
  return {
    index, setIndex, playing, speed, setSpeed, count,
    toggle: () => { if (index >= count - 1) setIndex(0); setPlaying((p) => !p); },
    step: () => { setPlaying(false); setIndex((i) => Math.min(count - 1, i + 1)); },
    back: () => { setPlaying(false); setIndex((i) => Math.max(0, i - 1)); },
    reset,
    finish: () => { setPlaying(false); setIndex(Math.max(0, count - 1)); },
  };
}
export type Player = ReturnType<typeof usePlayer>;

export function PlayerBar({ p, label }: { p: Player; label?: string }) {
  return (
    <div className="player">
      <IconButton icon="reset" label="Restart" onClick={() => p.reset()} />
      <IconButton icon="step" label="Previous step" onClick={p.back} />
      <button type="button" className="btn btn-primary btn-sm" onClick={p.toggle}><Icon name={p.playing ? "pause" : "play"} size={15} />{p.playing ? "Pause" : "Play"}</button>
      <IconButton icon="step" label="Next step" onClick={p.step} />
      <input type="range" min={0} max={Math.max(0, p.count - 1)} value={p.index} onChange={(e) => { p.setIndex(Number(e.target.value)); }} aria-label="Step" />
      <span className="mono dim">{label ?? `${p.index + 1} / ${p.count}`}</span>
      <select value={p.speed} onChange={(e) => p.setSpeed(Number(e.target.value))} aria-label="Speed">
        <option value={0.5}>0.5x</option><option value={1}>1x</option><option value={2}>2x</option><option value={4}>4x</option>
      </select>
    </div>
  );
}

export const pct = (n: number | null | undefined, d = 0) => (n === null || n === undefined ? "-" : `${(n * 100).toFixed(d)}%`);
export const ago = (iso: string) => {
  const s = Math.max(0, (Date.now() - new Date(iso + (iso.endsWith("Z") ? "" : "Z")).getTime()) / 1000);
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 129600) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
};
export function errText(e: unknown): string { return e instanceof Error ? e.message : String(e); }
