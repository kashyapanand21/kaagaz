from PIL import Image

from kaagaz.ai import classify as cl
from kaagaz.ai.client import CallInfo
from kaagaz.config import Settings
from kaagaz.db import connect
from kaagaz.schemas import Extraction


def ext(t: str, c: float = 0.9) -> Extraction:
    return Extraction(doc_type=t, confidence=c, summary="x")


def test_decide_rules():
    assert cl.decide(ext("marksheet_12"), "", 0.75)[0] == "indexed"
    assert cl.decide(ext("marksheet_12", 0.5), "", 0.75)[0] == "needs_review"
    assert cl.decide(ext("other"), "", 0.75)[0] == "needs_review"
    status, note = cl.decide(ext("marksheet_12"), "This is to certify... INCOME CERTIFICATE", 0.75)
    assert status == "needs_review" and "income_certificate" in note


def test_end_to_end_saves_only_scrubbed_text(tmp_path, monkeypatch):
    s = Settings(data_dir=tmp_path / "data")
    p = tmp_path / "IMG-WA0001.jpg"
    Image.new("RGB", (800, 600), "white").save(p)
    conn = connect(s.db_path)
    conn.execute("INSERT INTO documents (sha256, path, size_bytes, mtime) VALUES ('abc', ?, 1, 0)", (str(p),))
    conn.commit()

    raw = '{"doc_type":"aadhaar","confidence":0.5,"summary":"Aadhaar 1234 5678 9012","id_last4":"9012"}'
    monkeypatch.setattr(cl, "chat_json",
                        lambda *a, **k: (Extraction.model_validate_json(raw), CallInfo("fake", 1.0, raw=raw)))

    [(_, out)] = list(cl.classify_pending(conn, s))
    saved = conn.execute("SELECT * FROM documents").fetchone()
    conn.close()
    assert out.status == "needs_review"                       # 0.5 < 0.75
    assert "1234" not in saved["summary"] and "1234" not in saved["raw"]
    assert saved["id_last4"] == "9012"