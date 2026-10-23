from datetime import date

import pytest

from kaagaz.db import connect
from kaagaz.packets.checklist import load_checklist, save_checklist
from kaagaz.packets.matcher import match_items
from kaagaz.schemas import RequirementItem

TODAY = date(2026, 10, 23)
INCOME = RequirementItem(label="Income certificate", doc_types=["income_certificate"],
                         formats=["pdf"], issued_after=date(2026, 4, 1))
PHOTO = RequirementItem(label="Photo", doc_types=["photo"], formats=["jpg"])


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "k.sqlite")
    yield conn, tmp_path
    conn.close()


def add(db, name, doc_type, status="indexed", **cols):
    conn, folder = db
    p = folder / name
    p.write_bytes(b"x")
    row = {"sha256": name, "path": str(p), "size_bytes": 1, "mtime": 0,
           "status": status, "doc_type": doc_type, "confidence": 0.9, **cols}
    conn.execute(f"INSERT INTO documents ({','.join(row)}) VALUES ({','.join('?' * len(row))})",
                 tuple(row.values()))
    return p


def test_missing_when_library_has_none(db):
    [m] = match_items(db[0], [INCOME], today=TODAY)
    assert m.status == "missing" and m.best is None


def test_valid_beats_expired_and_expired_is_an_alternative(db):
    add(db, "old.jpg", "income_certificate", issue_date="2026-03-01")
    add(db, "new.jpg", "income_certificate", issue_date="2026-05-01")
    [m] = match_items(db[0], [INCOME], today=TODAY)
    assert m.status == "matched" and m.best.path.name == "new.jpg"
    assert m.alternatives[0].path.name == "old.jpg"


def test_only_expired_documents_mark_the_row_expired(db):
    add(db, "old.jpg", "income_certificate", issue_date="2026-03-01")
    [m] = match_items(db[0], [INCOME], today=TODAY)
    assert m.status == "expired" and any("form needs" in n for n in m.notes)


def test_confirmed_label_preferred_but_unconfirmed_still_usable(db):
    add(db, "unsure.jpg", "photo", status="needs_review")
    [m] = match_items(db[0], [PHOTO], today=TODAY)
    assert m.status == "matched" and any("not confirmed" in n for n in m.notes)
    add(db, "sure.jpg", "photo")
    [m] = match_items(db[0], [PHOTO], today=TODAY)
    assert m.best.path.name == "sure.jpg"


def test_deleted_file_is_skipped(db):
    add(db, "gone.jpg", "photo").unlink()
    [m] = match_items(db[0], [PHOTO], today=TODAY)
    assert m.status == "missing"


def test_profile_name_breaks_ties(db):
    add(db, "a.jpg", "photo", person_name="Someone Else")
    add(db, "b.jpg", "photo", person_name="Riya Sharma")
    [m] = match_items(db[0], [PHOTO], profile_name="Riya Sharma", today=TODAY)
    assert m.best.path.name == "b.jpg"


def test_checklist_json_round_trip(tmp_path):
    save_checklist([INCOME, PHOTO], tmp_path / "c.json")
    assert load_checklist(tmp_path / "c.json") == [INCOME, PHOTO]
    