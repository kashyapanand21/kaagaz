from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from kaagaz.schemas import RequirementItem

_ITEMS = TypeAdapter(list[RequirementItem])


def save_checklist(items: list[RequirementItem], path: Path) -> None:
    path.write_text(_ITEMS.dump_json(items, indent=2).decode("utf-8"), encoding="utf-8")


def load_checklist(path: Path) -> list[RequirementItem]:
    """Re-validated on load, so hand edits that break a rule (e.g. min > max) are caught."""
    return _ITEMS.validate_json(path.read_text(encoding="utf-8"))