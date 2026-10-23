import ollama
import pytest

from types import SimpleNamespace

from pydantic import BaseModel

import kaagaz.ai.client as client


class Ping(BaseModel):
    ok: bool


def fake(content: str):
    resp = SimpleNamespace(message=SimpleNamespace(content=content),
                           prompt_eval_count=5, eval_count=3)
    return SimpleNamespace(chat=lambda **kw: resp)


def test_valid_json(monkeypatch):
    monkeypatch.setattr(client, "_client", lambda: fake('{"ok": true}'))
    result, info = client.chat_json(Ping, "s", "p")
    assert result.ok and info.error is None


def test_bad_json_is_a_result_not_a_crash(monkeypatch):
    monkeypatch.setattr(client, "_client", lambda: fake("not json"))
    result, info = client.chat_json(Ping, "s", "p")
    assert result is None and "invalid JSON" in info.error and info.raw == "not json"

    


def test_server_crash_is_retried_once(monkeypatch):
    calls = []
    good = fake('{"ok": true}')

    def chat(**kw):
        calls.append(1)
        if len(calls) == 1:
            raise ollama.ResponseError("llama-server process has terminated", 500)
        return good.chat(**kw)

    monkeypatch.setattr(client, "_client", lambda: SimpleNamespace(chat=chat))
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    result, _ = client.chat_json(Ping, "s", "p")
    assert result.ok and len(calls) == 2


def test_two_crashes_pause_instead_of_failing_the_document(monkeypatch):
    def chat(**kw):
        raise ollama.ResponseError("llama-server process has terminated", 500)

    monkeypatch.setattr(client, "_client", lambda: SimpleNamespace(chat=chat))
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    with pytest.raises(client.OllamaUnavailable):
        client.chat_json(Ping, "s", "p")