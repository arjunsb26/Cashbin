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

# What the host accepts on these two parameters, read off the installed SDK (openai 3.16.2):
# openai.types.shared.reasoning_effort.ReasoningEffort and the service_tier hint on
# chat.completions.create. A value outside these is a 400 on every call.
REASONING_EFFORTS: tuple[str, ...] = ("none", "minimal", "low", "medium", "high")
SERVICE_TIERS: tuple[str, ...] = ("auto", "default", "flex", "scale", "priority", "fast")

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
    # How much better on carbon another option has to be before the tone stops calling the
    # bin a fine answer. The engine reads it, so it changes like every other threshold.
    tone_co2e_kg: float = Field(default=0.02, ge=0.0)
    # PLAN.md 21a item 37. How much better another option has to be before the bin says so
    # out loud. Under this it says "Fine to bin", because a bin that argues about three
    # cents is a bin nobody listens to.
    speak_up_cents: int = Field(default=100, ge=0)

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
    # No model name is written here on purpose: an empty model with a set provider is a
    # setup mistake worth seeing, not a silent default nobody chose.
    llm_provider: str = ""
    llm_base_url: str = ""
    llm_vision_model: str = ""
    llm_text_model: str = ""
    llm_agent_model: str = ""
    # Reasoning effort per call. The vision call has to land inside llm_timeout_s, and it
    # classifies a photograph rather than working anything out, so it thinks by default not
    # at all. The estimator does arithmetic on a price, so it keeps a low effort.
    llm_vision_effort: str = "none"
    llm_text_effort: str = "none"
    # The value estimate is off the critical path, and pricing a particular product off a
    # photograph is the one call here that is worth thinking about.
    llm_estimate_effort: str = "low"
    # How the host is asked to schedule the call. "fast" is the low latency queue; "default"
    # turns the request back into an ordinary one.
    llm_service_tier: str = "fast"
    # PLAN.md 21a item 35. On a cellular link calls took ten and fourteen seconds and the
    # person stood there holding a thing over a bin. Four seconds and then the ask, which
    # is an answer a person can act on rather than a wait with no end in sight.
    llm_timeout_s: float = Field(default=4.0, gt=0.0)
    # The longest side of the picture actually sent. The full size crop stays on disk for the
    # evidence drawer; the model is classifying a thing, not reading fine print.
    vision_image_max_px: int = Field(default=384, ge=64, le=4096)
    vision_image_quality: int = Field(default=80, ge=1, le=100)

    # Start the vision call when the step opens instead of when it settles. The settle alone
    # costs most of a second, and the picture is already good 300 ms after the item lands.
    identify_at_step_open: bool = True
    identify_open_delay_ms: int = Field(default=300, ge=0, le=5000)
    # Read from .env at startup. Never logged, never returned by any endpoint.
    openai_api_key: str = ""

    # Paths
    media_dir: Path = BACKEND_DIR / "media"
    db_path: Path = BACKEND_DIR / "binbooks.db"
    cert_dir: Path = REPO_DIR / "certs"
    recordings_dir: Path = BACKEND_DIR / "recordings"

    # Serving
    https_port: int = Field(default=8443, gt=0, le=65535)
    http_port: int = Field(default=8000, gt=0, le=65535)
    # Where the dashboard is being served. The backend sends the laptop there when someone
    # opens the backend's own address, and names it when an address has nothing at it.
    dashboard_url: str = "http://localhost:3000"

    # Off in the demo build. Gates /api/sim/* and every other dev-only surface.
    dev_tools: bool = False

    # Load the seed CSVs on a first start, when both seeded tables are still empty. On by
    # default, because an unseeded database has no catalog and no register and every
    # ticket would come back untracked. A test that wants an empty table turns it off.
    seed_on_start: bool = True

    @field_validator(
        "llm_provider",
        "llm_base_url",
        "llm_vision_model",
        "llm_text_model",
        "llm_agent_model",
        "llm_vision_effort",
        "llm_text_effort",
        "llm_estimate_effort",
        "llm_service_tier",
        "dashboard_url",
        "openai_api_key",
        "product_name",
        "product_short_name",
        "product_tagline",
        mode="before",
    )
    @classmethod
    def _clean_str(cls, value: Any) -> Any:
        return _clean(value) if isinstance(value, str) else value

    @field_validator("llm_vision_effort", "llm_text_effort", "llm_estimate_effort")
    @classmethod
    def _known_effort(cls, value: str) -> str:
        """An effort the host does not know is a 400 on every call, so refuse it here."""
        if value and value not in REASONING_EFFORTS:
            raise ValueError(f"reasoning effort must be one of {', '.join(REASONING_EFFORTS)}")
        return value

    @field_validator("llm_service_tier")
    @classmethod
    def _known_tier(cls, value: str) -> str:
        if value and value not in SERVICE_TIERS:
            raise ValueError(f"service tier must be one of {', '.join(SERVICE_TIERS)}")
        return value

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
    "tone_co2e_kg",
    "speak_up_cents",
    "step_min_g",
    "settle_ms",
    "bag_change_g",
    "confident_p",
    "min_margin",
    "memory_max_dist",
    "round_size",
    "llm_timeout_s",
    "llm_service_tier",
    "llm_vision_effort",
    "llm_text_effort",
    "llm_estimate_effort",
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
