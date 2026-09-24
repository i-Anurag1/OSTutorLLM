# OSTutorLLM 3.0 Architecture

Browser -> Next.js -> FastAPI -> PostgreSQL / local RAG / optional external LLM

The default path is local-first:

1. FastAPI seeds the database and indexes the bundled 16-file OS corpus.
2. Retrieval uses TF-IDF with unigram/bigram features plus lexical overlap.
3. AI Tutor returns a grounded local answer with source citations when no external LLM is configured.
4. An OpenAI-compatible Qwen/Llama endpoint can be enabled through environment variables without changing the UI.
5. Assessment is backed by a seeded question bank, so quiz/viva and scoring do not depend on a live model.
6. Simulator and code-lab endpoints execute deterministically with validation and resource limits.
