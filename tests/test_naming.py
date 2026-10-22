from kaagaz.engine.naming import render_name, unique
from kaagaz.schemas import DocType


def test_default_pattern_matches_wireframe():
    name, warns = render_name(None, "pdf", doctype=DocType.MARKSHEET_12, roll="12345")
    assert name == "12345_Marksheet12.pdf" and not warns


def test_missing_roll_drops_token_with_warning():
    name, warns = render_name(None, "jpg", doctype=DocType.PHOTO)
    assert name == "Photo.jpg" and warns


def test_unsafe_characters_cleaned():
    name, _ = render_name("{name}_{doctype}", "JPG", doctype=DocType.PHOTO,
                          name="Riya Sharma / B.Tech?")
    assert name == "Riya_Sharma_B.Tech_Photo.jpg"


def test_unknown_token_and_malformed_pattern():
    _, warns = render_name("{roll}_{father}", "jpg", doctype=DocType.PHOTO, roll="1")
    assert any("father" in w for w in warns)
    name, warns = render_name("{roll_{doctype}", "jpg", doctype=DocType.PHOTO, roll="12345")
    assert name == "12345_Photo.jpg" and warns


def test_max_len_keeps_extension():
    name, _ = render_name(None, "pdf", doctype=DocType.MARKSHEET_12, roll="12345", max_len=12)
    assert len(name) <= 12 and name.endswith(".pdf")


def test_unique_is_case_insensitive():
    taken: set[str] = set()
    assert unique("12345_Photo.jpg", taken) == "12345_Photo.jpg"
    assert unique("12345_photo.JPG", taken) == "12345_photo_2.JPG"