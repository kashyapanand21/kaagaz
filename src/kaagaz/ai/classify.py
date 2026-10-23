from __future__ import annotations

import io
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from PIL import Image

from kaagaz.ai.client import chat_json
from kaagaz.ai.scrub import scrub, scrub_model
from kaagaz.config import Settings
from kaagaz.dates import parse_printed_date
from kaagaz.engine.inkcheck import looks_like_signature
from kaagaz.engine.render import RenderError, render
from kaagaz.schemas import DocType, Extraction

SYSTEM = """You label Indian personal documents for a private, offline document assistant.
Look at the page image (and the PDF text, if given) and fill in the JSON fields.

Choose doc_type from the allowed list. Cues:
- marksheet_10: Class X / Secondary / Matriculation / माध्यमिक.
  marksheet_12: Class XII / Senior Secondary / Intermediate / उच्च माध्यमिक.
  semester_marksheet: a university semester grade card.
- degree_certificate vs provisional_certificate: if "provisional" is printed, it is provisional.
- income_certificate: आय प्रमाण पत्र. caste_certificate: जाति प्रमाण पत्र.
  domicile_certificate: निवास / residence certificate. ews_certificate: Economically Weaker Section.
- bank_passbook: the account-holder page of a passbook. cancelled_cheque: a cheque marked CANCELLED.
- photo: one person's face on a plain background, nothing else.
- signature: handwritten ink strokes (a name in cursive) on plain paper, with no printed text.
  It is often small, faint, or photographed at an angle. Never call a signature "other".
- thumb_impression: a fingerprint mark.
- Use "other" only if nothing fits.
Rules:
- person_name: the name of the person the document is about (student, applicant, account holder).
- issue_date and valid_until: copy the date EXACTLY as printed, in its original format.
  Use null if it is not printed. Never guess or calculate a date.
- year: the passing or issue year printed on the document.
- id_last4: only the LAST 4 digits of an ID number. Never write a full ID, account or PAN number
  anywhere, including the summary.
- confidence: how sure you are of doc_type, 0 to 1. Be honest: lower it for blurry, cropped or
  unusual documents.
- summary: one short line describing the document, with no ID numbers."""

TEXT_CUES = {
    DocType.INCOME_CERTIFICATE: ("income certificate", "आय प्रमाण"),
    DocType.CASTE_CERTIFICATE: ("caste certificate", "जाति प्रमाण"),
    DocType.DOMICILE_CERTIFICATE: ("domicile certificate", "residence certificate", "निवास प्रमाण"),
    DocType.EWS_CERTIFICATE: ("economically weaker section",),
    DocType.ADMIT_CARD: ("admit card", "hall ticket"),
}


def text_says(text: str) -> DocType | None:
    """The type the PDF text clearly names, if exactly one."""
    t = text.lower()
    hits = [dt for dt, cues in TEXT_CUES.items() if any(c in t for c in cues)]
    return hits[0] if len(hits) == 1 else None


def decide(e: Extraction, text: str, threshold: float) -> tuple[str, str | None]:
    if e.doc_type is DocType.OTHER:
        return "needs_review", "type: other"
    if e.confidence < threshold:
        return "needs_review", f"low confidence {e.confidence:.2f}"
    said = text_says(text)
    if said and said is not e.doc_type:
        return "needs_review", f"PDF text suggests {said.value}"
    return "indexed", None


@dataclass
class Outcome:
    status: str
    doc_type: str | None = None
    confidence: float | None = None
    seconds: float = 0.0
    note: str | None = None


def _save(conn: sqlite3.Connection, doc_id: int, **fields) -> None:
    cols = ", ".join(f"{k}=?" for k in fields)       # column names come from code, never input
    conn.execute(f"UPDATE documents SET {cols}, updated_at=datetime('now') WHERE id=?",
                 (*fields.values(), doc_id))
    conn.commit()                                     # one commit per document = resumable


def classify_one(conn: sqlite3.Connection, row: sqlite3.Row, s: Settings) -> Outcome:
    try:
        r = render(Path(row["path"]), s.thresholds.image_long_side)
    except (RenderError, OSError) as e:
        _save(conn, row["id"], status="failed", error=str(e))
        return Outcome("failed", note=str(e))

    thumb = s.thumbs_dir / f"{row['sha256']}.jpg"
    thumb.parent.mkdir(parents=True, exist_ok=True)
    thumb.write_bytes(r.thumb)

    prompt = "Label this document."
    if r.text:
        prompt += f"\n\nPDF text layer (may be incomplete):\n{r.text}"
    result, info = chat_json(Extraction, SYSTEM, prompt, images=r.images)   # may raise OllamaUnavailable
    common = dict(pages=r.pages, thumb=str(thumb), model=info.model, seconds=round(info.seconds, 2))

    if result is None:
        _save(conn, row["id"], status="needs_review", error=info.error, raw=scrub(info.raw), **common)
        return Outcome("needs_review", seconds=info.seconds, note=info.error)

    e = scrub_model(result)
    status, note = decide(e, r.text, s.thresholds.escalate_below)
    if e.doc_type is DocType.OTHER and looks_like_signature(Image.open(io.BytesIO(r.images[0]))):
        e = e.model_copy(update={"doc_type": DocType.SIGNATURE, "confidence": 0.0})  # code's suggestion, not the model's
        status, note = "needs_review", "looks like a signature (ink on plain paper); please confirm"

    issued = parse_printed_date(e.issue_date)                 # the model copies; code converts
    valid = parse_printed_date(e.valid_until)
    year = e.year or (issued.year if issued else None)

    _save(conn, row["id"], status=status, error=note,
          raw=scrub(info.raw) if status != "indexed" else None,
          doc_type=e.doc_type.value, confidence=e.confidence, person_name=e.person_name,
          issuer=e.issuer, year=year, language=e.language, summary=e.summary, id_last4=e.id_last4,
          issue_date=issued.isoformat() if issued else None,
          valid_until=valid.isoformat() if valid else None, **common)
    return Outcome(status, e.doc_type.value, e.confidence, info.seconds, note)


def classify_pending(conn: sqlite3.Connection, s: Settings,
                     limit: int | None = None) -> Iterator[tuple[sqlite3.Row, Outcome]]:
    sql = "SELECT id, path, sha256 FROM documents WHERE status='pending' ORDER BY id"
    rows = conn.execute(sql + (" LIMIT ?" if limit else ""), (limit,) if limit else ()).fetchall()
    for row in rows:
        yield row, classify_one(conn, row, s)


def reset_all(conn: sqlite3.Connection) -> int:
    n = conn.execute("UPDATE documents SET status='pending'").rowcount
    conn.commit()
    return n