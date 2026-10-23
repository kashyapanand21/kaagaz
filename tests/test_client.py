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