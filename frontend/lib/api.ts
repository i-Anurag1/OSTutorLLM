import type { ChatDone, Citation, RetrievalMeta } from "./types";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
let token = "";
export const setToken = (t: string) => { token = t; };
export const getToken = () => token;

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

function describe(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d))).join("; ");
  return `Request failed (${status})`;
}

async function request<T>(path: string, method: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API + path, {
      method, signal,
      headers: { ...(body !== undefined ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: "Bearer " + token } : {}) },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError("Cannot reach the API. Is the backend running at " + API + "?", 0);
  }
  if (!res.ok) {
    let detail: unknown = null;
    try { const j = await res.json(); detail = j.detail ?? j.error; } catch { /* non-JSON error body */ }
    throw new ApiError(describe(detail, res.status), res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T,>(p: string, signal?: AbortSignal) => request<T>(p, "GET", undefined, signal),
  post: <T,>(p: string, b?: unknown, signal?: AbortSignal) => request<T>(p, "POST", b ?? {}, signal),
  put: <T,>(p: string, b: unknown) => request<T>(p, "PUT", b),
  del: <T,>(p: string) => request<T>(p, "DELETE"),
  async upload<T>(p: string, file: File): Promise<T> {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(API + p, { method: "POST", body: form, headers: token ? { Authorization: "Bearer " + token } : {} });
    if (!res.ok) {
      let detail: unknown = null;
      try { detail = (await res.json()).detail; } catch { /* ignore */ }
      throw new ApiError(describe(detail, res.status), res.status);
    }
    return (await res.json()) as T;
  },
};

export interface StreamHandlers {
  onMeta: (m: { conversation_id: number; citations: Citation[]; retrieval: RetrievalMeta; abstain: boolean }) => void;
  onToken: (t: string) => void;
  onReplace: (t: string) => void;
  onDone: (d: ChatDone) => void;
}

/** Parse Server-Sent Events from the tutor stream. */
export function parseSse(buffer: string): { events: { event: string; data: string }[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events = parts.map((block) => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trim());
    }
    return { event, data: data.join("\n") };
  }).filter((e) => e.data);
  return { events, rest };
}

export async function streamChat(body: unknown, h: StreamHandlers, signal: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch(API + "/api/tutor/stream", {
      method: "POST", signal, body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError("Cannot reach the API. Is the backend running at " + API + "?", 0);
  }
  if (!res.ok || !res.body) {
    let detail: unknown = null;
    try { detail = (await res.json()).detail; } catch { /* ignore */ }
    throw new ApiError(describe(detail, res.status), res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSse(buffer);
    buffer = parsed.rest;
    for (const ev of parsed.events) {
      const data = JSON.parse(ev.data);
      if (ev.event === "meta") h.onMeta(data);
      else if (ev.event === "token") h.onToken(data.text);
      else if (ev.event === "replace") h.onReplace(data.text);
      else if (ev.event === "done") h.onDone(data);
      else if (ev.event === "error") throw new ApiError(data.detail || "Streaming error", 500);
    }
  }
}
