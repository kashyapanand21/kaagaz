from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from kaagaz.packets.validity import Validity, check_validity
from kaagaz.schemas import DocType, RequirementItem

MatchStatus = Literal["matched", "check_date", "expired", "missing"]
_VALIDITY_RANK = {"ok": 2, "check_date": 1, "expired": 0}
_ROW_STATUS = {"ok": "matched", "check_date": "check_date", "expired": "expired"}


@dataclass
class Candidate:
    id: int
    path: Path
    doc_type: DocType
    person_name: str | None
    year: int | None
    issue_date: date | None
    confidence: float
    confirmed: bool
    validity: Validity


@dataclass
class Match:
    item: RequirementItem
    status: MatchStatus
    best: Candidate | None = None
    alternatives: list[Candidate] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def name_score(person: str | None, profile_name: str) -> int:
    """+1 if the names share a word, -1 if both are known and don't, 0 if unknown."""
    if not person or not profile_name:
        return 0
    a = {w for w in profile_name.lower().split() if len(w) > 1}
    b = {w for w in person.lower().split() if len(w) > 1}
    return 1 if a & b else -1


def candidates(conn: sqlite3.Connection, item: RequirementItem,
               profile_name: str = "", today: date | None = None) -> list[Candidate]:
    types = [t.value for t in item.doc_types]
    rows = conn.execute(
        f"SELECT * FROM documents WHERE doc_type IN ({','.join('?' * len(types))}) "
        "AND status IN ('indexed', 'needs_review')", types)

    found: list[Candidate] = []
    for r in rows:
        path = Path(r["path"])
        if not path.exists():
            continue                                    # deleted or moved since the last scan
        issue = _date(r["issue_date"])
        validity = check_validity(DocType(r["doc_type"]), issue_date=issue,
                                  valid_until=_date(r["valid_until"]), year=r["year"],
                                  issued_after=item.issued_after, today=today)
        found.append(Candidate(r["id"], path, DocType(r["doc_type"]), r["person_name"], r["year"],
                               issue, r["confidence"] or 0.0, r["status"] == "indexed", validity))

    found.sort(key=lambda c: (_VALIDITY_RANK[c.validity.status],
                              c.confirmed,
                              name_score(c.person_name, profile_name),
                              c.issue_date or date(c.year or 1, 1, 1),
                              c.confidence),
               reverse=True)
    return found


def match_items(conn: sqlite3.Connection, items: list[RequirementItem],
                profile_name: str = "", today: date | None = None) -> list[Match]:
    matches: list[Match] = []
    for item in items:
        found = candidates(conn, item, profile_name, today)
        if not found:
            wanted = " / ".join(t.value for t in item.doc_types)
            matches.append(Match(item, "missing", notes=[f"no {wanted} in your library"]))
            continue

        best = found[0]
        notes: list[str] = []
        if best.validity.status != "ok" or best.validity.estimated:
            notes.append(best.validity.reason)
        if not best.confirmed:
            notes.append("label not confirmed yet (it's in the review queue)")
        if name_score(best.person_name, profile_name) < 0:
            notes.append("name on the document differs from your profile name")
        matches.append(Match(item, _ROW_STATUS[best.validity.status], best, found[1:4], notes))
    return matches