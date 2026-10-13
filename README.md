# OSTutor — a grounded Operating Systems tutor

Ask an Operating Systems question and get an answer built **only from your course material**, with every sentence marked by the
source that supports it. Around the tutor: step-through simulators, sandboxed code labs, quizzes with viva grading, a mastery
dashboard, and a retrieval lab that shows exactly what the tutor saw. Runs locally (Docker + Ollama), no cloud key needed.

```
 Next.js UI ──► FastAPI ──► hybrid RAG ──► Ollama (Qwen3 or your fine-tuned model)
   │              │  │          BM25 + TF-IDF now · BGE + FAISS when ready · rerank · MMR
   │              │  └─ PostgreSQL (users, progress, conversations)   Redis (cache, ingestion queue) ─► RQ worker
   └─ SSE streaming, evidence lanes, simulators, labs, quizzes
```

## Quick start
1. Install **Docker Desktop** and (recommended) **Ollama** (https://ollama.com/download).
2. Windows: double-click `RUN.bat`. macOS/Linux: `scripts/start.sh`. (First run pulls the model and builds the images.)
3. Open **http://localhost:3000** and use a demo account: `student@ostutor.local / Student123!`,
   `faculty@ostutor.local / Faculty123!`, `admin@ostutor.local / Admin123!`.

Without Ollama the app still works: answers are assembled directly from your notes ("extractive" mode, clearly badged).
Retrieval is usable immediately (keyword/BM25); the dense embedding model downloads in the background and upgrades search to
hybrid without a restart. Check **Knowledge → System** for the live status.

## What is in it
| Area | What you get |
|---|---|
| **Tutor** | Streaming answers, Teach / Socratic / Exam modes, adaptive level, conversation history, 👍/👎 feedback, follow-up suggestions. **Evidence lanes**: each sentence gets a coloured margin bar for the source that supports it; claims the evidence does not support get a dashed amber bar. `[S#]` chips open the exact passage. The tutor **declines** (and says so) when the notes do not cover the question. |
| **RAG** | Heading-aware chunking with section titles in every chunk · own BM25 + TF-IDF (uni/bigram) · glossary query expansion (LRU→least recently used, TLB, FCFS…) · dense BGE vectors (NumPy or FAISS) · weighted RRF fusion · optional cross-encoder rerank · MMR diversification · evidence-coverage confidence and abstention · fingerprinted index that rebuilds itself when documents change and reloads when the worker re-indexes. |
| **Simulators** | CPU scheduling (6 algorithms + compare), page replacement (FIFO/LRU/Optimal/Clock/LFU, Belady’s anomaly), paging + TLB, segmentation, disk scheduling (6), Banker’s algorithm with request check, producer–consumer, dining philosophers (naive deadlock + 3 fixes), thread life cycle. All step-through; all checked against textbook results. |
| **Code labs** | Python and shell sandboxes with 9 auto-graded exercises. Import allow-list, restricted bash with a whitelisted PATH, unprivileged user, CPU/memory/output limits. |
| **Practice** | 62 multiple-choice questions + 8 viva questions covering all 20 topics. **Scored on the server** (answers never reach the browser early). |
| **Knowledge** | Retrieval lab (per-stage scores), source upload with live indexing, benchmark evaluation, system status. |
| **Fine-tuning** | Original dataset + full QLoRA pipeline in `training/` — see its README. |

## Verification — what was actually run
| Check | Result | Where |
|---|---|---|
| Backend logic tests (RAG, grounding, simulators vs textbook values, sandbox security, LLM stream filter) | **77 pass** | `python scripts/verify.py` (no Docker needed) |
| Training pipeline tests (each preprocessing stage, split leakage, dataset format, metrics, label masking) | **13 pass** | same command |
| Retrieval benchmark (40 questions + 5 off-topic probes) | Recall@5 **1.00**, MRR **0.988**, nDCG@5 **0.991**, Hit@1 **0.975**, 0 false abstentions, 4/5 off-topic declined | Knowledge → Evaluation |
| Frontend strict TypeScript check + server-render of every screen with real simulator output | **clean, 28/28** | run during development |
| **Not run in the build environment** (no network, Docker or GPU there) | API layer with a live database, `docker compose up`, `next build`, dense/rerank models, real LLM output, **model training** | run `docker compose run --rm api pytest -q tests`, `npm run build`, and the training steps yourself |

Be aware of the limits: the benchmark was written together with the corpus, so it is a regression check rather than an unseen
test (every retrieval variant, even BM25 alone, scores near the ceiling on it — see `docs/evaluation.md`). Off-topic detection is a
heuristic (4 of 5 probes). The API tests exist and compile but were not executable where this was assembled.

## Fine-tuning (original dataset, preprocessed)
`training/` builds an original instruction dataset (corpus-derived answers, simulator-computed worked problems, quiz explanations,
abstention examples), applies a 9-stage preprocessing pipeline, and provides QLoRA training, GGUF export, an Ollama Modelfile and a
comparison script. **No trained weights are included** (no GPU was available); until you train one the app uses the stock model.
Details and the Colab notebook: `training/README.md`.

## Configuration (`.env`)
`LLM_MODEL` (default `qwen3:14b`; set `ostutor-qwen3` after fine-tuning) · `LLM_BASE_URL` (Ollama or any OpenAI-compatible server) ·
`EMBEDDING_MODEL`, `RERANKER_MODEL` · `RAG_MIN_COVERAGE` (abstention threshold) · `JWT_SECRET` (**change it** before sharing) ·
`CORS_ORIGINS`, `MAX_CODE_SECONDS`. See `.env.example`.

## Adding your own material
Sign in as faculty → **Knowledge → Sources** → drop a PDF/DOCX/PPTX/TXT/MD. Headings become citable sections. Indexing runs in the
background; the tutor uses the new material as soon as it finishes.

## Troubleshooting
* **“Model offline / missing”** pill: start Ollama and `ollama pull qwen3:14b` (or set `LLM_MODEL` to a model you have).
* **Keyword search instead of Hybrid**: the embedding model is still downloading (first start only) or could not be fetched — see Knowledge → System.
* **Port in use**: change the left side of `ports:` in `docker-compose.yml`.
* Logs: `docker compose logs api --tail=100`.

## Security notes
Code labs are sandboxed for a classroom setting (see `backend/app/code_runner.py`), not for hostile multi-tenant hosting: run the stack on a
trusted machine, change `JWT_SECRET`, and do not expose port 8000 publicly. The in-memory rate limiter is per API process.

## Layout
`backend/app` API, RAG, simulators, sandbox · `backend/data` corpus, benchmark, question bank · `backend/tests` · `frontend` Next.js UI ·
`training` dataset + fine-tuning · `docs` architecture and evaluation · `scripts` launchers and `verify.py`.
