from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import TypeVar

import httpx
import ollama
from pydantic import BaseModel, ValidationError

from kaagaz.config import get_settings

T = TypeVar("T", bound=BaseModel)
_NETWORK_ERRORS = (ConnectionError, httpx.ConnectError, httpx.TimeoutException)


class OllamaUnavailable(RuntimeError):
    """Ollama isn't running or the model isn't pulled. Pause work; don't fail documents."""


@dataclass
class CallInfo:
    model: str
    seconds: float
    prompt_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    raw: str = ""


@lru_cache(maxsize=1)
def _client() -> ollama.Client:
    return ollama.Client(host=get_settings().models.host, timeout=180)


def chat_json(schema: type[T], system: str, prompt: str,
              images: list[bytes] | None = None,
              model: str | None = None) -> tuple[T | None, CallInfo]:
    m = get_settings().models
    model = model or m.vision
    user: dict = {"role": "user", "content": prompt}
    if images:
        user["images"] = images

    t0 = time.perf_counter()
    try:
        resp = _client().chat(
            model=model,
            messages=[{"role": "system", "content": system}, user],
            format=schema.model_json_schema(),
            think=False,
            keep_alive=m.keep_alive,
            options={"temperature": 0, "num_ctx": m.num_ctx},
        )
    except _NETWORK_ERRORS as e:
        raise OllamaUnavailable(f"Ollama isn't reachable at {m.host}. Start the Ollama app.") from e
    except ollama.ResponseError as e:
        if e.status_code == 404:
            raise OllamaUnavailable(f"Model {model!r} isn't pulled. Run: ollama pull {model}") from e
        return None, CallInfo(model, time.perf_counter() - t0, error=f"ollama error: {e.error}")

    info = CallInfo(model, time.perf_counter() - t0,
                    resp.prompt_eval_count or 0, resp.eval_count or 0,
                    raw=resp.message.content or "")
    try:
        return schema.model_validate_json(info.raw), info
    except ValidationError as e:
        info.error = f"invalid JSON from model ({e.error_count()} error(s)): {e.errors()[0]['msg']}"
        return None, info


def health() -> list[str]:
    """Problems found. An empty list means ready."""
    m = get_settings().models
    try:
        pulled = {x.model for x in _client().list().models}
    except _NETWORK_ERRORS:
        return [f"Ollama isn't running at {m.host}. Start the Ollama app."]
    wanted = [name for name in (m.vision, m.escalation, m.embed) if name]
    return [f"Model {name} missing. Run: ollama pull {name}" for name in wanted if name not in pulled]