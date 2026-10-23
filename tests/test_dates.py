from datetime import date

from kaagaz.dates import parse_printed_date

TODAY = date(2026, 10, 23)
AUG5 = date(2025, 8, 5)


def test_day_first_numeric_formats():
    for text in ("05-08-2025", "05/08/2025", "5.8.2025", "05-08-25", "Date: 05/08/2025"):
        assert parse_printed_date(text, TODAY) == AUG5, text


def test_month_names_and_iso():
    for text in ("5 August 2025", "05 Aug, 2025", "5th Aug 2025", "August 5, 2025", "2025-08-05"):
        assert parse_printed_date(text, TODAY) == AUG5, text


def test_devanagari_digits():
    assert parse_printed_date("दिनांक ०५-०८-२०२५", TODAY) == AUG5


def test_garbage_is_rejected_not_stored():
    for text in ("0207-02-20", "1406-06-20", "31-02-2025", "no date", "", None):
        assert parse_printed_date(text, TODAY) is None, text