#!/usr/bin/env python3
"""One-command offline verification (no Docker, no GPU, no network): backend logic tests + training pipeline tests.

    pip install numpy scipy python-docx python-pptx pypdf
    python scripts/verify.py
The API integration tests (backend/tests/test_api.py) need the Docker stack: docker compose run --rm api pytest -q tests
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
steps = [
    ("backend unit tests (RAG, grounding, simulators, sandbox, LLM utils)", [sys.executable, "-m", "unittest", "tests.test_rag", "tests.test_simulators", "tests.test_code_runner", "tests.test_llm_utils"], ROOT / "backend"),
    ("training pipeline tests (preprocessing, dataset, metrics, masking)", [sys.executable, "training/test_training.py"], ROOT),
]
failed = 0
for name, cmd, cwd in steps:
    print(f"\n=== {name}")
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, "OSTUTOR_TEST_MODE": "1"})
    failed += r.returncode != 0
print("\nVERIFY:", "ALL PASSED" if not failed else f"{failed} step(s) FAILED")
sys.exit(1 if failed else 0)
