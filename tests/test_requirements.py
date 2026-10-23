from kaagaz.ai.requirements import ParsedItem, to_requirement

TEXT = "Photograph: JPG, 3.5 cm x 4.5 cm, size 20 KB to 50 KB. Marksheet: PDF up to 0.2 MB."
PHOTO_SRC = "Photograph: JPG, 3.5 cm x 4.5 cm, size 20 KB to 50 KB."


def item(**kw) -> ParsedItem:
    base = dict(label="Photo", source=PHOTO_SRC, doc_types=["photo"], formats=["jpg"])
    return ParsedItem(**(base | kw))


def test_grounded_numbers_not_flagged():
    r = to_requirement(item(min_kb=20, max_kb=50, width_cm=3.5, height_cm=4.5), TEXT)
    assert r.uncertain_fields == []


def test_mb_to_kb_conversion_is_grounded():
    r = to_requirement(item(label="Marksheet", source="Marksheet: PDF up to 0.2 MB.",
                            doc_types=["marksheet_12"], formats=["pdf"], max_kb=200), TEXT)
    assert r.uncertain_fields == []


def test_invented_limit_is_flagged():
    assert "max_kb" in to_requirement(item(max_kb=100), TEXT).uncertain_fields


def test_contradictions_repaired_not_fatal():
    r = to_requirement(item(min_kb=50, max_kb=20, width_cm=3.5), TEXT)
    assert (r.min_kb, r.max_kb) == (20, 50) and r.width_cm is None
    assert {"min_kb", "max_kb", "width_cm", "height_cm"} <= set(r.uncertain_fields)


def test_paraphrased_source_flags_label():
    assert "label" in to_requirement(item(source="photo must be jpg"), TEXT).uncertain_fields



def test_omitted_limits_are_flagged():
    r = to_requirement(item(max_kb=50), TEXT)          # model "forgot" min and the cm size
    assert {"min_kb", "width_cm", "height_cm"} <= set(r.uncertain_fields)


def test_class_number_and_dates_are_not_limits():
    src = "Class 12 marksheet issued on or after 01-04-2026, PDF, maximum 200 KB."
    r = to_requirement(ParsedItem(label="Marksheet", source=src, doc_types=["marksheet_12"],
                                  formats=["pdf"], max_kb=200), src)
    assert r.uncertain_fields == []