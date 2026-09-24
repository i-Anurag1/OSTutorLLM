import httpx
import re
import time

from .config import settings


async def generate(messages, temperature=0.2, response_format=None):
    if not settings.llm_base_url:
        return None, 0.0

    base_url = settings.llm_base_url.rstrip("/")

    # Native Ollama API for local Qwen/Llama models.
    # This avoids Qwen3 reasoning being returned separately by
    # Ollama's OpenAI-compatible endpoint.
    if "11434" in base_url:
        url = base_url.replace("/v1", "") + "/api/chat"

        body = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": 800,
            },
        }

        started = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=360) as client:
                response = await client.post(url, json=body)
                response.raise_for_status()
                data = response.json()

            content = data.get("message", {}).get("content", "")

            latency = round((time.perf_counter() - started) * 1000, 2)

            if content and content.strip():
                return content.strip(), latency

            return None, latency

        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            return None, round((time.perf_counter() - started) * 1000, 2)

    # Generic OpenAI-compatible API path.
    url = base_url + "/chat/completions"

    headers = {
        "Content-Type": "application/json",
    }

    if settings.llm_api_key:
        headers["Authorization"] = "Bearer " + settings.llm_api_key

    body = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 800,
    }

    if response_format:
        body["response_format"] = response_format

    started = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=360) as client:
            response = await client.post(
                url,
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        message = data["choices"][0]["message"]
        content = message.get("content") or ""

        latency = round((time.perf_counter() - started) * 1000, 2)

        if content.strip():
            return content.strip(), latency

        return None, latency

    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        return None, round((time.perf_counter() - started) * 1000, 2)


def grounded_validate(answer, citations, evidence=None):
    used = set(re.findall(r"\[S(\d+)\]", answer))
    ids = {c["id"][1:] for c in citations}

    if not citations or not used or not used.issubset(ids):
        return False

    if not evidence:
        return True

    sentences = re.split(r"(?<=[.!?])\s+", answer)

    for sentence in sentences:
        refs = set(re.findall(r"\[S(\d+)\]", sentence))

        if not refs:
            continue

        words = (
            set(re.findall(r"\b[a-zA-Z]{4,}\b", sentence.lower()))
            - {"source", "sources", "according"}
        )

        if not words:
            continue

        supported = False

        for ref in refs:
            idx = int(ref) - 1

            if 0 <= idx < len(evidence):
                src = set(
                    re.findall(
                        r"\b[a-zA-Z]{4,}\b",
                        evidence[idx]["text"].lower(),
                    )
                )

                if len(words & src) / len(words) >= 0.12:
                    supported = True
                    break

        if not supported:
            return False

    return True
