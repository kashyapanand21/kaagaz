import json
from datetime import date

from PIL import Image

from kaagaz.config import Profile, Settings
from kaagaz.db import connect
from kaagaz.packets.builder import build_packet
from kaagaz.packets.matcher import match_items
from kaagaz.schemas import RequirementItem
from tests.test_cleanup import signature_photo


def test_build_end_to_end(tmp_path):
    s = Settings(data_dir=tmp_path / "data", packets_dir=tmp_path / "Packets",
                 profile=Profile(name="Specimen Student", roll="12345"))
    docs = tmp_path / "docs"
    docs.mkdir()
    signature_photo().save(docs / "sign.jpg")
    Image.new("RGB", (2480, 3508), "white").save(docs / "marks.jpg")

    conn = connect(s.db_path)
    for fname, doc_type in [("sign.jpg", "signature"), ("marks.jpg", "marksheet_12")]:
        conn.execute("INSERT INTO documents (sha256, path, size_bytes, mtime, status, doc_type, confidence) "
                     "VALUES (?, ?, 1, 0, 'indexed', ?, 0.9)", (fname, str(docs / fname), doc_type))
    items = [
        RequirementItem(label="Signature", doc_types=["signature"], formats=["jpg"],
                        min_kb=1, max_kb=20, width_px=280, height_px=80, name_pattern="{roll}_Signature"),
        RequirementItem(label="Class 12 marksheet", doc_types=["marksheet_12"], formats=["pdf"], max_kb=200),
        RequirementItem(label="Income certificate", doc_types=["income_certificate"], formats=["pdf"], max_kb=300),
    ]
    matches = match_items(conn, items, s.profile.name, today=date(2026, 10, 23))
    conn.close()

    out_dir, rows = build_packet(matches, s, "NSP test")
    assert {r.label: r.status for r in rows} == {
        "Signature": "PASS", "Class 12 marksheet": "PASS", "Income certificate": "MISSING"}
    assert (out_dir / "12345_Signature.jpg").exists()
    assert (out_dir / "12345_Marksheet12.pdf").exists()
    assert len(json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))["rows"]) == 3
    assert (out_dir / "checklist.md").exists()
    assert (docs / "sign.jpg").exists() and (docs / "marks.jpg").exists()     # originals untouched