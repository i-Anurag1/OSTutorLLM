import type { CSSProperties, ReactNode } from "react";
import type { Support } from "./types";

export const LANES = ["var(--l1)", "var(--l2)", "var(--l3)", "var(--l4)", "var(--l5)", "var(--l6)", "var(--l7)", "var(--l8)"];
export const laneColor = (i: number) => LANES[((i % LANES.length) + LANES.length) % LANES.length];

export interface Block { kind: "p" | "li" | "oli" | "h" | "code"; text: string }

export function parseBlocks(src: string): Block[] {
  const out: Block[] = [];
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  let para: string[] = [];
  let code: string[] | null = null;
  const flush = () => { if (para.length) { out.push({ kind: "p", text: para.join(" ") }); para = []; } };
  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (code) { out.push({ kind: "code", text: code.join("\n") }); code = null; } else { flush(); code = []; }
      continue;
    }
    if (code) { code.push(line); continue; }
    const h = /^#{1,4}\s+(.*)$/.exec(line);
    const li = /^\s*[-*]\s+(.*)$/.exec(line);
    const oli = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (!line.trim()) flush();
    else if (h) { flush(); out.push({ kind: "h", text: h[1] }); }
    else if (li) { flush(); out.push({ kind: "li", text: li[1] }); }
    else if (oli) { flush(); out.push({ kind: "oli", text: oli[1] }); }
    else para.push(line.trim());
  }
  if (code) out.push({ kind: "code", text: code.join("\n") });
  flush();
  return out;
}

/** Inline formatting: `code`, **bold**, *italic* and [S#] citation chips. No HTML is ever injected. */
export function inline(text: string, onCite?: (n: number) => void): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*\s][^*]*\*|\[S\d+\])/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("`")) nodes.push(<code key={k++}>{tok.slice(1, -1)}</code>);
    else if (tok.startsWith("**")) nodes.push(<strong key={k++}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("[S")) {
      const n = Number(tok.slice(2, -1));
      nodes.push(
        <button key={k++} type="button" className="cite" style={{ background: laneColor(n - 1) }} onClick={() => onCite?.(n)} title={`Open source S${n}`}>
          {n}
        </button>
      );
    } else nodes.push(<em key={k++}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

const norm = (s: string) => s.replace(/^\s*([-*]|\d+[.)])\s+/, "").replace(/\*\*/g, "").trim();

/** Which lane (evidence source) supports a block, and whether any claim in it is unsupported. */
export function laneFor(block: Block, support?: Support): { lane: number | null; unsupported: boolean } {
  if (!support || block.kind === "code" || block.kind === "h") return { lane: null, unsupported: false };
  const text = norm(block.text);
  const sents = support.sentences.filter((s) => s.support !== null && text.includes(norm(s.text).replace(/\s+/g, " ")));
  if (!sents.length) return { lane: null, unsupported: false };
  const best = [...sents].sort((a, b) => (b.support ?? 0) - (a.support ?? 0))[0];
  return { lane: best.source ? best.source - 1 : null, unsupported: sents.some((s) => s.supported === false) };
}

export function Markdown({ text, support, onCite, lanes = false }: { text: string; support?: Support; onCite?: (n: number) => void; lanes?: boolean }) {
  const blocks = parseBlocks(text);
  const out: ReactNode[] = [];
  let list: { ordered: boolean; items: ReactNode[] } | null = null;
  const closeList = () => {
    if (!list) return;
    out.push(list.ordered ? <ol key={out.length}>{list.items}</ol> : <ul key={out.length}>{list.items}</ul>);
    list = null;
  };
  blocks.forEach((b, i) => {
    const info = lanes ? laneFor(b, support) : { lane: null, unsupported: false };
    const cls = info.unsupported ? "lane-bar unsupported" : info.lane !== null ? "lane-bar" : "";
    const style = info.lane !== null ? ({ "--lane": laneColor(info.lane) } as CSSProperties) : undefined;
    if (b.kind === "li" || b.kind === "oli") {
      const ordered = b.kind === "oli";
      if (!list || list.ordered !== ordered) { closeList(); list = { ordered, items: [] }; }
      list.items.push(<li key={i} className={cls} style={style} title={info.unsupported ? "Part of this line is not supported by the cited source" : undefined}>{inline(b.text, onCite)}</li>);
      return;
    }
    closeList();
    if (b.kind === "h") out.push(<h4 key={i}>{inline(b.text, onCite)}</h4>);
    else if (b.kind === "code") out.push(<pre key={i}><code>{b.text}</code></pre>);
    else out.push(<p key={i} className={cls} style={style} title={info.unsupported ? "Part of this paragraph is not supported by the cited source" : undefined}>{inline(b.text, onCite)}</p>);
  });
  closeList();
  return <div className="md">{out}</div>;
}
