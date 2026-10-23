from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _default_data_dir() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "Kaagaz"


class Models(BaseModel):
    vision: str = "gemma4:e4b"
    escalation: str | None = None      # set only after the VRAM test proves 12B fits
    embed: str | None = None           # P1: embeddings
    keep_alive: str = "15m"            # keep the model loaded between files (cold load ≈ 14 s)
    num_ctx: int = 8192                # the 32k default wastes VRAM on a 6 GB card
    host: str = "http://127.0.0.1:11434"

    @field_validator("host")
    @classmethod
    def _local_only(cls, v: str) -> str:
        host = urlparse(v).hostname
        if host not in LOCAL_HOSTS:
            raise ValueError(f"Ollama host must be local (privacy rule), got {host!r}")
        return v


class Thresholds(BaseModel):
    escalate_below: float = 0.75
    review_below: float = 0.60
    image_long_side: int = 1024
    min_file_kb: int = 10
    max_file_mb: int = 40


class Profile(BaseModel):
    name: str = ""
    roll: str = ""


class Settings(BaseModel):
    folders: list[Path] = Field(default_factory=list)
    data_dir: Path = Field(default_factory=_default_data_dir)
    packets_dir: Path = Field(default_factory=lambda: Path.home() / "Documents" / "Kaagaz" / "Packets")
    extensions: frozenset[str] = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".heic", ".webp"})
    models: Models = Field(default_factory=Models)
    thresholds: Thresholds = Field(default_factory=Thresholds)
    profile: Profile = Field(default_factory=Profile)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "kaagaz.sqlite"

    @property
    def thumbs_dir(self) -> Path:
        return self.data_dir / "thumbs"


def load_settings(path: Path | None = None) -> Settings:
    path = path or Path(os.environ.get("KAAGAZ_CONFIG", "config.toml"))
    if not path.exists():
        return Settings()
    with path.open("rb") as f:
        return Settings.model_validate(tomllib.load(f))


@lru_cache
def get_settings() -> Settings:
    return load_settings()