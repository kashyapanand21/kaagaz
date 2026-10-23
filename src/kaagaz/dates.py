from __future__ import annotations

import re
from datetime import date

_DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_NUMERIC = re.compile(r"\b(\d{1,4})[-/.](\d{1,2})[-/.](\d{2,4})\b")
_DAY_MONTH = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b")
_MONTH_DAY = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b")


def _make(y: int, m: int | None, d: int, today: date) -> date | None:
    if m is None:
        return None
    if y < 100:                                             # two-digit year: 25 -> 2025, 98 -> 1998
        y += 2000 if y <= today.year % 100 + 1 else 1900
    try:
        result = date(y, m, d)
    except ValueError:
        return None                                         # e.g. 31-02-2025
    return result if date(1950, 1, 1) <= result <= date(today.year + 30, 12, 31) else None


def parse_printed_date(text: str | None, today: date | None = None) -> date | None:
    """A date as printed on an Indian document. Day-first: 05-08-2025 is 5 August 2025."""
    if not text:
        return None
    today = today or date.today()
    t = text.translate(_DEVANAGARI)
    if m := _NUMERIC.search(t):
        a, b, c = (int(x) for x in m.groups())
        if len(m.group(1)) == 4:
            return _make(a, b, c, today)                    # ISO: 2025-08-05
        return _make(c, b, a, today)                        # day-first: 05-08-2025
    if m := _DAY_MONTH.search(t):
        return _make(int(m.group(3)), _MONTHS.get(m.group(2)[:3].lower()), int(m.group(1)), today)
    if m := _MONTH_DAY.search(t):
        return _make(int(m.group(3)), _MONTHS.get(m.group(1)[:3].lower()), int(m.group(2)), today)
    return None