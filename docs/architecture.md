# Architecture

## Request flow (tutor)
1. **Contextualise** — a short follow-up ("what about LRU?") is prefixed with the previous question for retrieval only.
2. **Retrieve** (`rag.search`) — glossary expansion (expansion terms weigh 0.4 vs the student’s own words) → BM25 and uni/bigram
   TF-IDF candidates → dense BGE candidates when embeddings exist → weighted reciprocal-rank fusion → optional cross-encoder
   rerank → MMR (λ 0.72) to avoid five near-identical chunks.
3. **Decide** — *evidence coverage* = IDF-weighted share of the question’s key terms present in the top-3 chunks (terms absent from
   the whole corpus count most). Below `RAG_MIN_COVERAGE` the tutor declines instead of calling the model.
4. **Generate** — `tutor.build_messages` formats numbered evidence `[S#]`, mode and level instructions; the LLM streams over SSE
   (`<think>` blocks are filtered). If the model is unreachable the answer is assembled extractively with the same citation format.
5. **Check** — `grounding.support_report` scores every sentence against its cited chunk; unknown citation ids are stripped; the
   UI renders the result as evidence lanes. Answers, citations and the report are stored with the conversation.

## Two-phase index
Phase 1 (sparse, ~20 ms for 105 chunks) publishes immediately; phase 2 computes embeddings in a background thread and upgrades the
same in-memory index. Manifest + corpus fingerprint on disk let the API reuse a valid index at start-up, rebuild when documents
changed, and reload when the RQ worker re-indexes (the API watches the manifest’s mtime). Without `sentence-transformers`/FAISS the
system degrades to sparse retrieval and NumPy inner product respectively; nothing crashes.

## Chunking
Markdown headings (and DOCX heading styles, PPTX slide titles) define sections; each chunk keeps `title › section` which is also
prepended to the indexed text. Chunks are ≤900 characters with ≤120 characters of word-aligned overlap inside a section.

## Data model
Existing tables are unchanged (`users, topics, progress, activities, chat_logs, sources, questions, ingestion_jobs, audit_logs`).
New: `conversations`, `messages` (citations, grounding metadata, feedback). `Base.metadata.create_all` creates them on an existing
database without migrating old rows.

## Security model
JWT auth, RBAC (`student` < `faculty` < `admin`), PBKDF2 password hashing, login and lab rate limits, server-side quiz scoring,
conversation ownership checks. Code labs: see `backend/app/code_runner.py` header for the layered sandbox and its limits.
