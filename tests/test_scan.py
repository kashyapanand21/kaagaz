import os
from pathlib import Path

import pytest

from kaagaz.config import Settings
from kaagaz.db import connect, counts
from kaagaz.scan import scan


def put(p: Path, kb: int = 20, data: bytes | None = None) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if data is not None else os.urandom(kb * 1024))


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    s = Settings(folders=[root], data_dir=tmp_path / "data", packets_dir=root / "Packets")
    conn = connect(s.db_path)
    yield root, s, conn
    conn.close()


def test_finds_supported_files_and_skips_the_rest(env):
    root, s, conn = env
    put(root / "IMG-20240612-WA0007.jpg")
    put(root / "old" / "marks.PDF")
    put(root / "notes.txt")
    put(root / "tiny.jpg", kb=2)
    put(root / "Packets" / "12345_Photo.jpg")        # our own output: never indexed
    assert scan(conn, s).new == 2
    assert counts(conn) == {"pending": 2}


def test_rescan_is_free_and_renames_keep_the_document(env):
    root, s, conn = env
    put(root / "a.jpg")
    scan(conn, s)
    assert scan(conn, s).unchanged == 1
    (root / "a.jpg").rename(root / "renamed.jpg")
    rep = scan(conn, s)
    assert rep.moved == 1 and counts(conn) == {"pending": 1}


def test_duplicate_copies_are_one_document(env):
    root, s, conn = env
    data = os.urandom(20 * 1024)
    put(root / "a.jpg", data=data)
    put(root / "copy of a.jpg", data=data)
    rep = scan(conn, s)
    assert rep.new == 1 and rep.duplicate == 1


def test_missing_folder_is_reported(tmp_path):
    s = Settings(folders=[tmp_path / "nope"], data_dir=tmp_path / "data")
    conn = connect(s.db_path)
    rep = scan(conn, s)
    conn.close()
    assert rep.missing_folders and rep.seen == 0