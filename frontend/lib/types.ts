export type Role = "student" | "faculty" | "admin";
export interface User { id: number; email: string; name: string; role: Role }
export interface Topic { id: number; name: string; description: string; difficulty: string; questions: number }

export interface Citation {
  id: string; source: string; path: string; title: string; section: string; page: number; chunk: number;
  score: number; scores: Record<string, number | null>; type: string; text: string;
}
export interface SupportSentence { text: string; refs: number[]; support: number | null; supported: boolean | null; source: number | null; cited: boolean }
export interface Support { sentences: SupportSentence[]; support_score: number; supported_ratio: number; citation_ratio: number }
export interface RetrievalMeta {
  ready: boolean; mode: string; dense_used: boolean; rerank_used: boolean; expanded_terms: string[]; candidates: number;
  coverage: number; confidence: number; abstain: boolean; latency_ms: Record<string, number>;
}
export interface ChatMsg {
  id?: number; role: "user" | "assistant"; content: string; citations?: Citation[]; support?: Support; grounded?: boolean;
  mode?: string; model?: string; latency_ms?: number; suggestions?: string[]; feedback?: number | null; streaming?: boolean;
  retrieval?: RetrievalMeta; abstained?: boolean; confidence?: number;
}
export interface ChatDone {
  answer: string; citations: Citation[]; grounded: boolean; support: Support; suggestions: string[]; conversation_id: number;
  message_id: number; latency_ms: number; retrieval: RetrievalMeta; model: string; mode: string; abstained: boolean; confidence: number;
}
export interface ConversationSummary { id: number; title: string; topic: string | null; updated_at: string }

export interface Health {
  status: string; version: string; rag_ready: boolean; llm_mode: string;
  llm: { provider: string; model: string; reachable: boolean; model_available: boolean | null; error: string | null };
  rag: RagStatus;
}
export interface RagStatus {
  ready: boolean; indexing: boolean; chunks: number; sources: number; mode: string; dense_ready: boolean; embedding_model: string;
  reranker_model: string; vector_store: string; sparse_retrieval: string; embedding_error: string | null; reranker_error: string | null;
  last_error: string | null; fingerprint: string | null;
}
export interface Hit { id: string; source: string; section: string; title: string; text: string; rank: number; score: number; scores: Record<string, number | null>; page: number }
export interface SearchResult { hits: Hit[]; meta: RetrievalMeta }
export interface SourceRow { id: number; name: string; status: string; version: number; chunks: number; checksum: string; created_at: string }

export interface TopicProgress { topic_id: number; name: string; difficulty: string; mastery: number; attempts: number; correct: number }
export interface Dashboard {
  overall: number; topics: TopicProgress[]; attempted: number; streak_days: number; weakest: TopicProgress[]; next_topic: string | null;
  activity: { kind: string; topic: string; score: number; created_at: string }[];
}
export interface QuizQuestion { id: number; question: string; options: string[] | null; difficulty: string; kind: string }
export interface QuizResult { score: number; correct: number; total: number; mastery: number | null; recommendation: string; results: { id: number; correct: boolean; given: string; answer: string; explanation: string }[] }
export interface VivaResult { score: number; verdict: string; model_answer: string; covered_terms: string[]; missing_terms: string[] }
export interface Exercise { id: string; language: "python" | "shell"; topic: string; difficulty: string; title: string; prompt: string; hint: string; starter: string; expected_stdout: string }
export interface RunResult { ok: boolean; stdout: string; stderr: string; exit_code: number; timed_out: boolean; duration_ms: number }
export interface TestResult { passed: boolean; actual_stdout: string; stderr: string; expected_stdout: string; hint: string | null; duration_ms: number }

export interface EvalAggregate { [k: string]: number | null }
export interface RetrievalEval { k: number; benchmark_size: number; out_of_scope: number; aggregate: EvalAggregate; cases: { id: string; query: string; recall_at_k: number; mrr: number; hit_at_1: number; top_source: string | null; abstained: boolean }[]; oos_cases: { query: string; abstained: boolean }[] }
export interface AnswerEval { benchmark_size: number; model: string; llm_cases: number; aggregate: EvalAggregate; cases: { id: string; query: string; answer_mode: string; latency_ms: number; groundedness: number; concept_coverage: number; citation_correctness: number }[] }
export interface SystemStatus { version: string; llm: Health["llm"]; rag: RagStatus; settings: Record<string, string | number>; counts: Record<string, number> }
export interface StudentRow { id: number; name: string; email: string; role: string; mastery: number }
export interface Analytics { users: number; sources: number; questions: number; activities: number; chat_sessions: number; avg_latency_ms: number; grounded_rate: number; thumbs_up: number; thumbs_down: number; rag_chunks: number }

// ---- simulators
export interface CpuResult {
  algorithm: string; timeline: { pid: string; start: number; end: number; remaining: number }[];
  metrics: { pid: string; arrival: number; burst: number; completion: number; waiting: number; turnaround: number; response: number }[];
  avg_waiting: number; avg_turnaround: number; avg_response: number; cpu_utilization: number; throughput: number; context_switches: number; makespan: number;
}
export interface CpuCompare { rows: { algorithm: string; avg_waiting: number; avg_turnaround: number; avg_response: number; context_switches: number }[]; best_waiting: string }
export interface PageStep { index: number; reference: number; frames: (number | null)[]; hit: boolean; fault: boolean; victim: number | null; slot: number; ref_bits: number[] | null }
export interface PageResult { algorithm: string; frames: number; faults: number; hits: number; fault_rate: number; hit_ratio: number; steps: PageStep[] }
export interface PageCompare { rows: { algorithm: string; faults: number }[]; belady: { frames: number; faults: number }[]; belady_anomaly: boolean }
export interface DiskResult { algorithm: string; order: number[]; movement: number; segments: { from: number; to: number; distance: number }[]; path: number[]; average_seek: number; disk_size: number }
export interface BankerResult {
  safe: boolean; sequence: number[]; need: number[][]; work: number[];
  steps: { process: number; need: number[]; work_before: number[]; work_after: number[] }[];
  request?: { process: number; vector: number[]; granted: boolean; reason: string; sequence_after: number[] };
}
export interface PCEvent { tick: number; actor: string; action: string; item: number | null; buffer: number[]; empty: number; full: number; note: string }
export interface PCResult { events: PCEvent[]; buffer_size: number; items: number; ticks: number; peak_occupancy: number; producer_blocked: number; consumer_blocked: number }
export interface DiningEvent { step: number; philosopher: number; action: string; note: string; forks: (number | null)[]; states: string[]; meals: number[] }
export interface DiningResult { strategy: string; n: number; events: DiningEvent[]; deadlock: boolean; deadlock_at: number | null; meals: number[]; explanation: string }
export interface PagingRow { logical: number; page: number; offset: number; tlb: string; fault: boolean; frame: number; physical: number; victim_page: number | null; page_table: Record<string, number>; tlb_state: number[] }
export interface PagingResult { rows: PagingRow[]; faults: number; tlb_hits: number; tlb_hit_ratio: number; offset_bits: number | null; formula: string }
export interface SegResult { rows: { segment: number; offset: number; base: number | null; limit: number | null; valid: boolean; physical: number | null; reason: string }[]; rule: string }
export interface ThreadResult { states: string[]; threads: string[]; trace: { t: number; states: Record<string, string> }[]; quantum: number }
