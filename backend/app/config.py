"""Every tunable in one place. Env overrides it, /api/settings overrides a subset at runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
BRAND_FILE = REPO_DIR / "brand.json"

_BRAND_FALLBACK = {
    "name": "BinBooks",
    "short_name": "BinBooks",
    "tagline": "A trash can that does the books",
}


def _clean(value: str) -> str:
    """Drop the trailing carriage return that Windows-authored .env files carry."""
    return value.rstrip("\r\n").strip()


def load_brand(path: Path | None = None) -> dict[str, str]:
    """Read brand.json. It is the one place the product name is written."""
    target = path or BRAND_FILE
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_BRAND_FALLBACK)
    if not isinstance(raw, dict):
        return dict(_BRAND_FALLBACK)
    return {key: _clean(str(raw.get(key, default))) for key, default in _BRAND_FALLBACK.items()}


class Settings(BaseSettings):
    """All tunables from PLAN.md section 18 plus the four the step 0 brief adds.

    Field names are lowercase. Environment lookup is case insensitive, so the uppercase
    names PLAN.md uses (DB_PATH, LLM_PROVIDER and friends) set these fields directly.
    """

    model_config = SettingsConfigDict(
        env_file=str(REPO_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Brand. Defaults come from brand.json, env still wins.
    product_name: str = Field(default_factory=lambda: load_brand()["name"])
    product_short_name: str = Field(default_factory=lambda: load_brand()["short_name"])
    product_tagline: str = Field(default_factory=lambda: load_brand()["tagline"])

    # Money and policy
    tax_rate: float = Field(default=0.21, ge=0.0, le=1.0)
    capitalization_threshold_cents: int = Field(default=50_000, ge=0)
    disposal_fee_cents: int = Field(default=0, ge=0)
    recycle_fee_cents: int = Field(default=0, ge=0)

    # Step detection
    step_min_g: float = Field(default=3.0, gt=0.0)
    settle_ms: int = Field(default=600, gt=0)
    bag_change_g: float = Field(default=200.0, gt=0.0)

    # Identification confidence
    confident_p: float = Field(default=0.80, ge=0.0, le=1.0)
    min_margin: float = Field(default=0.25, ge=0.0, le=1.0)
    memory_max_dist: float = Field(default=0.35, ge=0.0, le=2.0)

    # Rounds
    round_size: int = Field(default=20, gt=0)

    # LLM access. Empty provider means the stub provider, which needs no key.
    llm_provider: str = ""
    llm_vision_model: str = ""
    llm_text_model: str = ""
    llm_timeout_s: float = Field(default=8.0, gt=0.0)

    # Paths
    media_dir: Path = BACKEND_DIR / "media"
    db_path: Path = BACKEND_DIR / "binbooks.db"
    cert_dir: Path = REPO_DIR / "certs"
    recordings_dir: Path = BACKEND_DIR / "recordings"

    # Serving
    https_port: int = Field(default=8443, gt=0, le=65535)
    http_port: int = Field(default=8000, gt=0, le=65535)

    # Off in the demo build. Gates /api/sim/* and every other dev-only surface.
    dev_tools: bool = False

    @field_validator(
        "llm_provider",
        "llm_vision_model",
        "llm_text_model",
        "product_name",
        "product_short_name",
        "product_tagline",
        mode="before",
    )
    @classmethod
    def _clean_str(cls, value: Any) -> Any:
        return _clean(value) if isinstance(value, str) else value

    @field_validator("media_dir", "db_path", "cert_dir", "recordings_dir", mode="before")
    @classmethod
    def _clean_path(cls, value: Any) -> Any:
        return Path(_clean(value)) if isinstance(value, str) else value

    @property
    def cert_file(self) -> Path:
        return self.cert_dir / "dev-cert.pem"

    @property
    def key_file(self) -> Path:
        return self.cert_dir / "dev-key.pem"


# The keys /api/settings may change while the app runs. Everything else needs a restart.
RUNTIME_SETTING_KEYS: tuple[str, ...] = (
    "tax_rate",
    "capitalization_threshold_cents",
    "disposal_fee_cents",
    "recycle_fee_cents",
    "step_min_g",
    "settle_ms",
    "bag_change_g",
    "confident_p",
    "min_margin",
    "memory_max_dist",
    "round_size",
    "llm_timeout_s",
)

_settings: Settings | None = None


def get_settings() -> Settings:
    """One process-wide Settings instance. Tests call reset_settings between cases."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings(replacement: Settings | None = None) -> Settings:
    """Replace the cached settings. Used by tests and by the run script."""
    global _settings
    _settings = replacement if replacement is not None else Settings()
    return _settings
