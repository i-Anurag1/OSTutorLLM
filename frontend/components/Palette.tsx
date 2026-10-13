"use client";
import { useEffect, useRef, useState } from "react";
import { Icon } from "../lib/icons";
import type { IconName } from "../lib/icons";
import { cx } from "./ui";

export interface Command { id: string; label: string; hint?: string; icon: IconName; run: () => void }

export function Palette({ open, onClose, commands, onAsk }: { open: boolean; onClose: () => void; commands: Command[]; onAsk: (q: string) => void }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement | null>(null);
  useEffect(() => { if (open) { setQ(""); setSel(0); setTimeout(() => input.current?.focus(), 20); } }, [open]);
  if (!open) return null;
  const needle = q.trim().toLowerCase();
  const items: Command[] = commands.filter((c) => !needle || (c.label + " " + (c.hint ?? "")).toLowerCase().includes(needle));
  if (needle.length > 2) items.push({ id: "ask", label: `Ask the tutor: ${q.trim()}`, icon: "spark", run: () => onAsk(q.trim()) });
  const go = (c?: Command) => { if (c) { onClose(); c.run(); } };
  return (
    <div className="palette-wrap" onClick={onClose}>
      <div className="palette" role="dialog" aria-label="Command palette" onClick={(e) => e.stopPropagation()}>
        <div className="palette-input"><Icon name="search" size={17} />
          <input ref={input} value={q} onChange={(e) => { setQ(e.target.value); setSel(0); }} placeholder="Jump to a page, open a simulator, or ask a question…"
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(items.length - 1, s + 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
              else if (e.key === "Enter") go(items[sel]);
            }} aria-label="Command" />
        </div>
        <ul className="palette-list">
          {items.length === 0 && <li className="dim pad">No matches</li>}
          {items.map((c, i) => (
            <li key={c.id}><button type="button" className={cx("palette-item", i === sel && "on")} onMouseEnter={() => setSel(i)} onClick={() => go(c)}><Icon name={c.icon} size={16} /><span>{c.label}</span>{c.hint && <span className="dim small">{c.hint}</span>}</button></li>
          ))}
        </ul>
      </div>
    </div>
  );
}
