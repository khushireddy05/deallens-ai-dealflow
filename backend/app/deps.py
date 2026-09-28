from functools import lru_cache
from pathlib import Path

from fastapi import Depends
from sqlalchemy.orm import Session

from .config import get_settings
from .crm.postgres import PostgresCRM
from .db import get_session
from .enrichment.base import EnrichmentProvider
from .enrichment.website import WebsiteEnrichment
from .llm.base import LLMClient
from .llm.openai_client import MissingKeyExtractor, OpenAIExtractor
from .llm.replay import ReplayExtractor
from .pipeline import PipelineDeps
from .screening import Thesis, load_thesis


@lru_cache
def _thesis(path: Path) -> Thesis:
    return load_thesis(path)


@lru_cache
def _replay(path: Path) -> ReplayExtractor:
    return ReplayExtractor.from_file(path)


@lru_cache
def _openai(api_key: str, model: str, timeout: float, attempts: int) -> OpenAIExtractor:
    return OpenAIExtractor(api_key, model, timeout=timeout, max_attempts=attempts)


def get_thesis() -> Thesis:
    return _thesis(get_settings().thesis_path)


def get_llm() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "replay":
        return _replay(settings.samples_path)
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            return MissingKeyExtractor()
        return _openai(
            settings.openai_api_key,
            settings.openai_model,
            settings.llm_timeout,
            settings.llm_max_attempts,
        )
    raise RuntimeError(f"Unknown LLM_PROVIDER {settings.llm_provider!r} (use 'openai' or 'replay')")


def get_enricher() -> EnrichmentProvider | None:
    settings = get_settings()
    if not settings.enrichment_enabled:
        return None
    return WebsiteEnrichment(timeout=settings.enrichment_timeout)


def get_crm(session: Session = Depends(get_session)) -> PostgresCRM:
    return PostgresCRM(session)


def get_pipeline(
    crm: PostgresCRM = Depends(get_crm),
    llm: LLMClient = Depends(get_llm),
    enricher: EnrichmentProvider | None = Depends(get_enricher),
    thesis: Thesis = Depends(get_thesis),
) -> PipelineDeps:
    return PipelineDeps(crm=crm, llm=llm, enricher=enricher, thesis=thesis)
