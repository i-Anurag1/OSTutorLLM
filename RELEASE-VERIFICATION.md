# OSTutorLLM release verification

Release date: 2026-10-22

## Changes made
- Fixed the CI-only login rate-limit collision by widening login and lab limits only when OSTUTOR_TEST_MODE=1. Production limits stay unchanged (12 logins/minute and 40 lab calls/minute).
- Added LLM_REQUIRED configuration. Docker Compose defaults to LLM_REQUIRED=1 for local use; when the configured model is unavailable, non-test tutor generation returns an explicit HTTP 503 rather than silently returning an extractive answer. Test mode and intentional LLM_REQUIRED=0 retain the extractive path.
- Updated Windows and Linux/macOS launchers to check/start Ollama, confirm the configured model is installed, run a live LLM smoke check, build/start Docker Compose in the background, wait for the web UI, and show logs.
- Improved the live LLM smoke test to handle host.docker.internal in the .env and report model-not-installed errors clearly.
- CI and TEST-ALL explicitly set test-mode variables to prevent local-model dependency in tests.
- Removed stale .bak copies and the generated frontend tsconfig build-info file.
- De-duplicated backend requirements and added a small Python syntax-check script.
- Updated README startup/troubleshooting documentation.

## Checks completed in this environment
- Python AST syntax validation: PASS, 31 backend Python files.
- backend/tests/test_llm_utils.py: PASS, 10 tests (includes strict required-LLM behavior).
- backend/tests/test_simulators.py: PASS, 30 tests.
- Python YAML parsing of docker-compose.yml and .github/workflows/ci.yml: PASS.
- GitHub Actions failure log reviewed: 87 API integration tests passed; two failed because the in-process login rate limiter returned 429 in test_retrieval_lab_and_evaluation and test_full_system_end_to_end. The test-mode throttle change directly addresses this cause.
- Full local verification is limited here: Docker and Ollama are not installed, outbound package downloads are blocked, and the available runtime differs from the project's Python 3.12 container. The sandbox subprocess tests timed out in this restricted environment. A clean API/Postgres/Redis integration run, real Ollama response, frontend build, model training, and deployment must be confirmed on a normal host/CI run.

## Model / fine-tuning status
The source repository's training README and project README state that no trained model weights are included. This ZIP contains the fine-tuning scripts and datasets, not a trained Qwen checkpoint. No fine-tuning was performed during this release because no GPU/training runtime or network is available in this environment. The launcher checks the configured model exists; set LLM_MODEL=qwen3:14b for the stock model or LLM_MODEL=ostutor-qwen3 after you build/import your fine-tuned Ollama model.
