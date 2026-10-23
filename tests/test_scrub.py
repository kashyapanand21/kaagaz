from kaagaz.ai.scrub import scrub, scrub_model
from kaagaz.schemas import DocType, Extraction


def test_aadhaar_grouped_and_plain():
    assert scrub("UID 1234 5678 9012") == "UID XXXX XXXX 9012"
    assert scrub("123456789012") == "XXXX XXXX 9012"


def test_pan_any_case():
    assert scrub("PAN: abcde1234f") == "PAN: XXXXXX234F"


def test_account_masked_but_dates_untouched():
    assert (scrub("A/c 123456789012345, issued 01-04-2026 in 2026")
            == "A/c XXXX2345, issued 01-04-2026 in 2026")


def test_model_strings_scrubbed_enum_kept():
    e = Extraction(doc_type="aadhaar", confidence=0.9, id_last4="9012",
                   summary="Aadhaar 1234 5678 9012 of a specimen student")
    s = scrub_model(e)
    assert "1234" not in s.summary and s.doc_type is DocType.AADHAAR