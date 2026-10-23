from datetime import date

from kaagaz.packets.validity import check_validity
from kaagaz.schemas import DocType

TODAY = date(2026, 10, 23)
APRIL = date(2026, 4, 1)
INC = DocType.INCOME_CERTIFICATE


def test_printed_expiry_in_past_is_expired():
    v = check_validity(DocType.PASSPORT, valid_until=date(2026, 3, 1), today=TODAY)
    assert v.status == "expired" and "printed" in v.reason


def test_portal_rule_with_exact_date():
    assert check_validity(INC, issue_date=date(2026, 3, 15), issued_after=APRIL, today=TODAY).status == "expired"
    assert check_validity(INC, issue_date=date(2026, 5, 1), issued_after=APRIL, today=TODAY).status == "ok"


def test_portal_rule_with_year_only():
    assert check_validity(INC, year=2025, issued_after=APRIL, today=TODAY).status == "expired"
    assert check_validity(INC, year=2026, issued_after=APRIL, today=TODAY).status == "check_date"


def test_portal_rule_beats_future_printed_expiry():
    v = check_validity(INC, issue_date=date(2026, 3, 1), valid_until=date(2027, 3, 1),
                       issued_after=APRIL, today=TODAY)
    assert v.status == "expired"


def test_estimate_never_says_expired():
    old = check_validity(INC, issue_date=date(2025, 1, 10), today=TODAY)
    assert old.status == "check_date" and old.estimated and "probably expired" in old.reason
    new = check_validity(INC, issue_date=date(2026, 6, 1), today=TODAY)
    assert new.status == "ok" and new.estimated


def test_year_range_straddling_cutoff_is_check_date():
    assert check_validity(INC, year=2025, today=TODAY).status == "check_date"


def test_marksheet_never_expires_but_passport_needs_a_date():
    assert check_validity(DocType.MARKSHEET_12, today=TODAY).status == "ok"
    assert check_validity(DocType.PASSPORT, today=TODAY).status == "check_date"