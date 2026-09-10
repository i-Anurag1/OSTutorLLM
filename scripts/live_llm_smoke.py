"""Smoke-test a real OpenAI-compatible Qwen/Llama chat endpoint.

Usage:
  python scripts/live_llm_smoke.py

Environment:
  LLM_BASE_URL, LLM_API_KEY (optional), LLM_MODEL
"""
import json
import os
import sys
from pathlib import Path
import urllib.error
import urllib.request

def load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
model = os.environ.get("LLM_MODEL", "Qwen/Qwen3-14B")
key = os.environ.get("LLM_API_KEY", "")

if not base:
    print("FAIL: LLM_BASE_URL is not configured.", file=sys.stderr)
    raise SystemExit(2)

url = base + "/chat/completions"
payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "You are an OS tutor. Answer briefly."},
        {"role": "user", "content": "What is a process in an operating system?"},
    ],
    "temperature": 0,
    "max_tokens": 120,
}
headers = {"Content-Type": "application/json"}
if key:
    headers["Authorization"] = "Bearer " + key

req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
try:
    with urllib.request.urlopen(req, timeout=60) as response:
        data = json.load(response)
except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
    print(f"FAIL: LLM endpoint request failed: {exc}", file=sys.stderr)
    raise SystemExit(1)

try:
    content = data["choices"][0]["message"]["content"]
except (KeyError, IndexError, TypeError) as exc:
    print(f"FAIL: unexpected OpenAI-compatible response: {exc}", file=sys.stderr)
    raise SystemExit(1)

if not isinstance(content, str) or not content.strip():
    print("FAIL: endpoint returned an empty assistant message.", file=sys.stderr)
    raise SystemExit(1)

print("PASS: live LLM endpoint responded successfully")
print("model:", model)
print("answer:", content.strip())
