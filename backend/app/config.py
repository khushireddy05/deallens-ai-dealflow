import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value and value.strip() else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value and value.strip() else default


@dataclass(frozen=True)
class Settings:
    database_url: str
    llm_provider: str
    openai_api_key: str | None
    openai_model: str
    llm_timeout: float
    llm_max_attempts: int
    enrichment_enabled: bool
    enrichment_timeout: float
    thesis_path: Path
    samples_path: Path
    cors_origins: list[str]
    seed_on_start: bool


def get_settings() -> Settings:
    """Read settings from the environment on every call so tests can override them."""
    origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
    return Settings(
        database_url=os.environ.get("DATABASE_URL") or "sqlite:///./dealflow.db",
        llm_provider=(os.environ.get("LLM_PROVIDER") or "openai").strip().lower(),
        openai_api_key=(os.environ.get("OPENAI_API_KEY") or "").strip() or None,
        openai_model=(os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip(),
        llm_timeout=_env_float("LLM_TIMEOUT", 30.0),
        llm_max_attempts=_env_int("LLM_MAX_ATTEMPTS", 3),
        enrichment_enabled=_env_bool("ENRICHMENT_ENABLED", True),
        enrichment_timeout=_env_float("ENRICHMENT_TIMEOUT", 5.0),
        thesis_path=Path(os.environ.get("THESIS_PATH") or BASE_DIR / "thesis.json"),
        samples_path=Path(
            os.environ.get("SAMPLES_PATH") or DATA_DIR / "sample_pitches.json"
        ),
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        seed_on_start=_env_bool("SEED_ON_START", False),
    )
