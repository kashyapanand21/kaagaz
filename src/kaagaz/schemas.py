from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class DocType(StrEnum):
    # identity
    AADHAAR = "aadhaar"
    PAN = "pan"
    VOTER_ID = "voter_id"
    PASSPORT = "passport"
    DRIVING_LICENCE = "driving_licence"
    # education
    MARKSHEET_10 = "marksheet_10"
    MARKSHEET_12 = "marksheet_12"
    SEMESTER_MARKSHEET = "semester_marksheet"
    DEGREE_CERTIFICATE = "degree_certificate"
    PROVISIONAL_CERTIFICATE = "provisional_certificate"
    MIGRATION_CERTIFICATE = "migration_certificate"
    TRANSFER_CERTIFICATE = "transfer_certificate"
    ADMIT_CARD = "admit_card"
    # certificates
    CASTE_CERTIFICATE = "caste_certificate"
    INCOME_CERTIFICATE = "income_certificate"
    DOMICILE_CERTIFICATE = "domicile_certificate"
    EWS_CERTIFICATE = "ews_certificate"
    DISABILITY_CERTIFICATE = "disability_certificate"
    CHARACTER_CERTIFICATE = "character_certificate"
    # finance
    BANK_PASSBOOK = "bank_passbook"
    CANCELLED_CHEQUE = "cancelled_cheque"
    FEE_RECEIPT = "fee_receipt"
    # personal
    PHOTO = "photo"
    SIGNATURE = "signature"
    THUMB_IMPRESSION = "thumb_impression"
    # other
    RESUME = "resume"
    OFFER_LETTER = "offer_letter"
    OTHER = "other"


IMAGE_ONLY_TYPES = frozenset({DocType.PHOTO, DocType.SIGNATURE, DocType.THUMB_IMPRESSION})

class Extraction(BaseModel):
    # Every key is REQUIRED in the schema sent to Ollama (null still allowed): with optional keys
    # the model skipped person_name, year and dates on every document. Python defaults stay for tests.
    model_config = ConfigDict(json_schema_extra=lambda s, _: s.update(required=list(s["properties"])))

    doc_type: DocType
    confidence: float = Field(ge=0, le=1, description="Your confidence in doc_type, from 0 to 1")
    person_name: str | None = Field(None, description="Full name of the person the document belongs to, exactly as printed")
    issuer: str | None = Field(None, description="Issuing board, office or institution, as printed")
    year: int | None = Field(None, description="Passing or issue year as printed, 4 digits")
    issue_date: str | None = Field(None, description="Issue date copied EXACTLY as printed (e.g. 05/08/2025 or 5 August 2025), or null if not printed")
    valid_until: str | None = Field(None, description="Expiry / 'valid up to' date copied EXACTLY as printed, or null if not printed")
    id_last4: str | None = Field(None, description="ONLY the last 4 digits of any ID number. Never the full number.")
    language: str = Field("en", description="Main language code, e.g. en, hi")
    summary: str = Field(description="One short line describing the document, used for search")

    @field_validator("id_last4", mode="before")
    @classmethod
    def _keep_last4(cls, v: object) -> str | None:
        if v is None:
            return None
        digits = re.sub(r"\D", "", str(v))
        return digits[-4:] if len(digits) >= 4 else None

    @field_validator("year", mode="before")
    @classmethod
    def _plausible_year(cls, v: object) -> int | None:
        try:
            year = int(v)
        except (TypeError, ValueError):
            return None
        return year if 1950 <= year <= 2100 else None       # repair, don't reject the whole result

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp(cls, v: object) -> float:
        try:
            return min(max(float(v), 0.0), 1.0)
        except (TypeError, ValueError):
            return 0.0


Format = Literal["pdf", "jpg", "png"]


class RequirementItem(BaseModel):
    label: str
    doc_types: list[DocType] = Field(min_length=1)
    formats: list[Format] = Field(min_length=1)
    min_kb: int | None = Field(None, ge=1)
    max_kb: int | None = Field(None, ge=1)
    width_px: int | None = Field(None, gt=0)
    height_px: int | None = Field(None, gt=0)
    width_cm: float | None = Field(None, gt=0)
    height_cm: float | None = Field(None, gt=0)
    dpi: int | None = Field(None, gt=0)
    background: Literal["white", "light", "any"] = "any"
    pages: Literal["single", "merge_all", "first_only"] = "single"
    name_pattern: str | None = None
    issued_after: date | None = Field(None, description="Only if the portal says the document must be issued after a date")
    mandatory: bool = True
    uncertain_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> RequirementItem:
        if self.min_kb and self.max_kb and self.min_kb > self.max_kb:
            raise ValueError(f"min_kb {self.min_kb} > max_kb {self.max_kb}")
        if (self.width_px is None) != (self.height_px is None):
            raise ValueError("width_px and height_px must be given together")
        if (self.width_cm is None) != (self.height_cm is None):
            raise ValueError("width_cm and height_cm must be given together")
        return self