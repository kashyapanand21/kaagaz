from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Literal

from kaagaz.schemas import DocType

Status = Literal["ok", "expired", "check_date"]

MUST_PRINT_EXPIRY = frozenset({DocType.PASSPORT, DocType.DRIVING_LICENCE})
TYPICAL_MONTHS = {                       # rules of thumb, always labelled as estimates
    DocType.INCOME_CERTIFICATE: 12,
    DocType.EWS_CERTIFICATE: 12,
    DocType.CHARACTER_CERTIFICATE: 6,
}


@dataclass(frozen=True)
class Validity:
    status: Status
    reason: str
    estimated: bool = False


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def fmt(d: date) -> str:
    return d.strftime("%d %b %Y")

def _portal_rule(issue_date: date | None, year: int | None, after: date) -> Validity:
    need = f"form needs issued on or after {fmt(after)}"
    if issue_date:
        if issue_date < after:
            return Validity("expired", f"issued {fmt(issue_date)}; {need}")
        return Validity("ok", f"issued {fmt(issue_date)}; meets the form's date rule")
    if year and year < after.year:
        return Validity("expired", f"issued in {year}; {need}")
    if year and year > after.year:
        return Validity("ok", f"issued in {year}; meets the form's date rule")
    return Validity("check_date", f"exact issue date not found; {need}")


def _estimate(doc_type: DocType, issue_date: date | None, year: int | None,
              months: int, today: date) -> Validity:
    name = doc_type.value.replace("_", " ")
    typical = f"{name}s are usually valid about {months} months"
    if issue_date:
        earliest = latest = issue_date
        when = fmt(issue_date)
    elif year:
        earliest, latest, when = date(year, 1, 1), date(year, 12, 31), str(year)
    else:
        return Validity("check_date", f"no issue date found; {typical}")

    if add_months(latest, months) < today:
        return Validity("check_date", f"probably expired: issued {when}; {typical}", estimated=True)
    if add_months(earliest, months) >= today:
        return Validity("ok", f"probably valid until ~{fmt(add_months(earliest, months))} "
                              f"(estimate: {typical})", estimated=True)
    return Validity("check_date", f"issued {when}; may have expired ({typical})", estimated=True)

def check_validity(doc_type: DocType, *, issue_date: date | None = None,
                   valid_until: date | None = None, year: int | None = None,
                   issued_after: date | None = None, today: date | None = None) -> Validity:
    today = today or date.today()

    if valid_until and valid_until < today:                  # 1. printed expiry, past: final
        return Validity("expired", f"expired on {fmt(valid_until)} (printed)")

    if issued_after:                                         # 2. the portal's rule
        rule = _portal_rule(issue_date, year, issued_after)
        if rule.status != "ok":
            return rule

    if valid_until:
        return Validity("ok", f"valid until {fmt(valid_until)} (printed)")
    if issued_after:
        return rule
    if doc_type in MUST_PRINT_EXPIRY:
        return Validity("check_date", "expiry date not found; it is printed on this document")

    months = TYPICAL_MONTHS.get(doc_type)                    # 3. labelled estimate
    if months is None:
        return Validity("ok", "does not expire")
    return _estimate(doc_type, issue_date, year, months, today)   # 4. or CHECK DATE inside

