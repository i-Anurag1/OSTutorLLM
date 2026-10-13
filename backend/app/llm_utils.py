"""Pure helpers for LLM output handling (no network, no settings) so they are unit-testable."""
from __future__ import annotations

import json
import re

_THINK = re.compile(r"<think>.*?</think>", re.S)


def strip_think(text: str) -> str:
    """Remove Qwen3-style reasoning blocks, including an unterminated trailing block."""
    text = _THINK.sub("", text)
    if "<think>" in text:
        text = text.split("<think>", 1)[0]
    return text.strip()


class ThinkFilter:
    """Streaming filter that drops <think>...</think> content even when tags are split across chunks."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self.buf = ""
        self.inside = False

    def feed(self, delta: str) -> str:
        self.buf += delta
        out = ""
        while True:
            if self.inside:
                i = self.buf.find(self.CLOSE)
                if i < 0:
                    self.buf = self.buf[-(len(self.CLOSE) - 1):]
                    return out
                self.buf = self.buf[i + len(self.CLOSE):]
                self.inside = False
                continue
            i = self.buf.find(self.OPEN)
            if i >= 0:
                out += self.buf[:i]
                self.buf = self.buf[i + len(self.OPEN):]
                self.inside = True
                continue
            keep = 0
            for k in range(1, len(self.OPEN)):
                if self.buf.endswith(self.OPEN[:k]):
                    keep = k
            cut = len(self.buf) - keep
            out += self.buf[:cut]
            self.buf = self.buf[cut:]
            return out

    def flush(self) -> str:
        rest = "" if self.inside else self.buf
        self.buf, self.inside = "", False
        return rest


def parse_ollama_line(line: str) -> tuple[str, bool]:
    """One NDJSON line of Ollama's /api/chat stream -> (text delta, done)."""
    line = line.strip()
    if not line:
        return "", False
    obj = json.loads(line)
    return (obj.get("message") or {}).get("content", "") or "", bool(obj.get("done"))


def parse_openai_line(line: str) -> tuple[str, bool]:
    """One SSE line of an OpenAI-compatible stream -> (text delta, done)."""
    line = line.strip()
    if not line.startswith("data:"):
        return "", False
    payload = line[5:].strip()
    if payload == "[DONE]":
        return "", True
    choices = json.loads(payload).get("choices") or [{}]
    return (choices[0].get("delta") or {}).get("content") or "", False


def model_listed(model: str, names: list[str]) -> bool:
    """Ollama lists 'name:tag'; a bare name means ':latest'."""
    wanted = model if ":" in model else model + ":latest"
    return any(n == model or n == wanted for n in names)
