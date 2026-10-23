from __future__ import annotations

import re
from enum import Enum
from typing import TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


def _last4(m: re.Match) -> str:
    return re.sub(r"\W", "", m.group())[-4:].upper()


_RULES = [
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b"), lambda m: "XXXX XXXX XXXX " + _last4(m)),  # Aadhaar VID
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"),           lambda m: "XXXX XXXX " + _last4(m)),       # Aadhaar
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.I),            lambda m: "XXXXXX" + _last4(m)),           # PAN
    (re.compile(r"\b\d{9,18}\b"),                            lambda m: "XXXX" + _last4(m)),             # accounts, phones
]


def scrub(text: str | None) -> str | None:
    if not text:
        return text
    for pattern, replace in _RULES:
        text = pattern.sub(replace, text)
    return text


def scrub_model(obj: M) -> M:
    """Scrub every plain-string field of a Pydantic model (enums are left alone)."""
    updates = {name: scrub(value) for name, value in obj
               if isinstance(value, str) and not isinstance(value, Enum)}
    return obj.model_copy(update=updates)