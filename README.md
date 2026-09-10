# OSTutorLLM 3.0 · Local-First Operating Systems AI Lab

A ready-to-run academic SI/project package for Operating Systems learning. The stack ships with a preloaded OS source corpus, a local grounded tutor fallback, question bank, simulators, Python and shell labs, analytics, JWT/RBAC, source ingestion, and a professional responsive web UI.

## Zero-config launch

Install Docker Desktop, extract this folder, then from the project root run:

```powershell
docker compose up --build
```

Open `http://localhost:3000`.

API docs: `http://localhost:8000/docs`
Health: `http://localhost:8000/health`

No source upload is required. The bundled 16-file OS corpus is indexed automatically on startup. No external LLM API key is required for the default local-grounded tutor and bundled assessment flow. An OpenAI-compatible Qwen/Llama endpoint can be enabled later with environment variables.

## Evaluation accounts

Student: `student@ostutor.local` / `Student123!`
Faculty: `faculty@ostutor.local` / `Faculty123!`
Admin: `admin@ostutor.local` / `Admin123!`

## Included

AI Tutor with evidence citations; hybrid TF-IDF retrieval; bundled OS corpus; quiz/viva bank and scoring; CPU scheduling, page replacement, Banker/deadlock, disk scheduling, paging, segmentation, producer-consumer, dining philosophers and thread lifecycle simulators; restricted Python and shell labs; persistent mastery analytics; faculty/admin source management; PDF/PPTX/DOCX/TXT/MD ingestion; JWT/RBAC; PostgreSQL and Redis; Docker health checks; responsive UI.

## Optional external LLM

Set `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in a local `.env`. The default app continues to work without those values.

## One-command restart

```powershell
docker compose up -d --build
```

## Troubleshooting

`docker compose logs api --tail=100`

`docker compose logs web --tail=100`

`docker compose ps`

The API deliberately returns readable JSON error details, and the UI surfaces them without leaving the user on an endless loading state.
