"""LLM client: Ollama native API (default) or any OpenAI-compatible endpoint. Imports httpx lazily."""
from __future__ import annotations

import time
from typing import AsyncIterator

from .config import settings
from .llm_utils import ThinkFilter, model_listed, parse_ollama_line, parse_openai_line, strip_think

last_error: str | None = None
_ping_cache: dict = {"at": 0.0, "value": None}


class LLMError(RuntimeError):
    pass


def _ollama() -> bool:
    return "11434" in settings.llm_base_url or "ollama" in settings.llm_base_url.lower()


def _root() -> str:
    base = settings.llm_base_url.rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def _timeout():
    import httpx

    return httpx.Timeout(settings.llm_timeout, connect=4.0)


def _request(messages: list[dict], temperature: float | None, stream: bool) -> tuple[str, dict, dict]:
    temp = settings.llm_temperature if temperature is None else temperature
    if _ollama():
        body = {"model": settings.llm_model, "messages": messages, "stream": stream, "think": False,
                "options": {"temperature": temp, "num_predict": settings.llm_num_predict, "num_ctx": settings.llm_num_ctx}}
        return _root() + "/api/chat", body, {}
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = "Bearer " + settings.llm_api_key
    body = {"model": settings.llm_model, "messages": messages, "temperature": temp,
            "max_tokens": settings.llm_num_predict, "stream": stream}
    return settings.llm_base_url.rstrip("/") + "/chat/completions", body, headers


async def generate(messages: list[dict], temperature: float | None = None) -> tuple[str | None, float]:
    """Return (answer or None when the model is unreachable, latency in ms)."""
    global last_error
    if not settings.llm_base_url:
        return None, 0.0
    import httpx

    url, body, headers = _request(messages, temperature, False)
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            r = await client.post(url, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
        content = data["message"]["content"] if _ollama() else data["choices"][0]["message"]["content"]
        last_error = None
        text = strip_think(content or "")
        return (text or None), round((time.perf_counter() - started) * 1000, 2)
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
        last_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        return None, round((time.perf_counter() - started) * 1000, 2)


async def stream(messages: list[dict], temperature: float | None = None) -> AsyncIterator[str]:
    """Yield text deltas. Raises LLMError if the model cannot be reached before any token arrives."""
    global last_error
    if not settings.llm_base_url:
        raise LLMError("LLM_BASE_URL is not configured")
    import httpx

    url, body, headers = _request(messages, temperature, True)
    parse = parse_ollama_line if _ollama() else parse_openai_line
    filt = ThinkFilter()
    got_any = False
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            async with client.stream("POST", url, json=body, headers=headers) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    delta, done = parse(line)
                    text = filt.feed(delta) if delta else ""
                    if text:
                        got_any = True
                        yield text
                    if done:
                        break
        tail = filt.flush()
        if tail:
            yield tail
        last_error = None
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        last_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        if not got_any:
            raise LLMError(last_error) from exc


async def ping(max_age: float = 15.0) -> dict:
    """Is the model server reachable and is the configured model installed? Cached briefly."""
    now = time.time()
    if _ping_cache["value"] is not None and now - _ping_cache["at"] < max_age:
        return _ping_cache["value"]
    info = {"provider": "ollama" if _ollama() else "openai-compatible", "model": settings.llm_model, "reachable": False,
            "model_available": None, "models": [], "error": None, "last_error": last_error}
    if not settings.llm_base_url:
        info["error"] = "LLM_BASE_URL is not set"
    else:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=httpx.Timeout(2.5)) as client:
                if _ollama():
                    r = await client.get(_root() + "/api/tags")
                    r.raise_for_status()
                    names = [m.get("name", "") for m in r.json().get("models", [])]
                    info.update(reachable=True, models=names[:30], model_available=model_listed(settings.llm_model, names))
                else:
                    headers = {"Authorization": "Bearer " + settings.llm_api_key} if settings.llm_api_key else {}
                    r = await client.get(settings.llm_base_url.rstrip("/") + "/models", headers=headers)
                    info["reachable"] = r.status_code < 500
        except Exception as exc:
            info["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    _ping_cache.update(at=now, value=info)
    return info
