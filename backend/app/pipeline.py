"""The triage pipeline: enrich -> extract -> validate -> screen -> deduplicate -> save.

Design rules:
- The raw pitch is committed before any processing (nothing is lost, FR-25).
- Each step commits its result. A retry reuses stored results instead of repeating them.
- Failures are recorded on the opportunity and in `processing_log`; they are never raised
  to the caller.
"""

import logging
from dataclasses import dataclass

from .crm.base import CRMClient
from .enrichment.base import EnrichmentError, EnrichmentProvider
from .llm.base import ExtractionError, LLMClient
from .models import Company, Opportunity
from .normalize import build_pitch_text, first_domain, idempotency_key, normalize_domain
from .schemas import CompanyData, ExtractedCompany, PitchIn
from .screening import Thesis, screen

logger = logging.getLogger(__name__)


class OpportunityNotFound(Exception):
    pass


class NotRetryable(Exception):
    pass


class StepFailure(Exception):
    def __init__(self, step: str, message: str):
        super().__init__(message)
        self.step = step
        self.message = message


@dataclass
class PipelineDeps:
    crm: CRMClient
    llm: LLMClient
    enricher: EnrichmentProvider | None
    thesis: Thesis


def validate_extraction(extracted: ExtractedCompany) -> None:
    """Business rules checked before anything is written to the CRM (FR-15)."""
    missing = []
    if not (extracted.company_name or "").strip():
        missing.append("company_name")
    if not ((extracted.description or "").strip() or (extracted.product or "").strip()):
        missing.append("description or product")
    if missing:
        raise StepFailure("validated", f"Missing required field(s): {', '.join(missing)}")


_SCREENED_FIELDS = ("country", "industry", "product", "description", "funding_stage")


def _fill_gaps(extracted: ExtractedCompany, known: Company | None) -> tuple[ExtractedCompany, bool]:
    """Fill fields the pitch left empty from the matching CRM company. Pitch values win."""
    if known is None:
        return extracted, False
    updates = {}
    for field in _SCREENED_FIELDS:
        if getattr(extracted, field) in (None, "", "unknown"):
            fallback = getattr(known, field)
            if fallback and fallback != "unknown":
                updates[field] = fallback
    return (extracted.model_copy(update=updates), True) if updates else (extracted, False)


def submit_pitch(deps: PipelineDeps, pitch: PitchIn) -> tuple[Opportunity, bool]:
    """Store a pitch and process it. Returns (opportunity, created).

    Submitting the same pitch again returns the existing opportunity untouched.
    """
    key = idempotency_key(pitch.source, pitch.sender, pitch.subject, pitch.body)
    opportunity, created = deps.crm.create_opportunity(pitch, key)
    if not created:
        return opportunity, False
    deps.crm.add_log(opportunity, "received", "ok")
    run_pipeline(deps, opportunity)
    return opportunity, True


def retry_opportunity(deps: PipelineDeps, opportunity_id: int) -> Opportunity:
    opportunity = deps.crm.get_opportunity(opportunity_id)
    if opportunity is None:
        raise OpportunityNotFound(opportunity_id)
    if opportunity.processing_state == "completed":
        raise NotRetryable("This opportunity was already processed successfully")
    run_pipeline(deps, opportunity)
    return opportunity


def run_pipeline(deps: PipelineDeps, opportunity: Opportunity) -> None:
    crm = deps.crm
    step = "received"
    try:
        crm.mark_processing(opportunity)
        text = build_pitch_text(opportunity.subject, opportunity.raw_body)

        # 1. Enrichment (never fatal, FR-6)
        step = "enriched"
        if opportunity.enrichment is not None:
            crm.add_log(opportunity, "enriched", "skipped", "Reusing stored enrichment")
        elif deps.enricher is None:
            crm.add_log(opportunity, "enriched", "skipped", "Enrichment is disabled")
        else:
            domain = first_domain(text)
            if domain is None:
                crm.add_log(opportunity, "enriched", "skipped", "No website found in the pitch")
            else:
                try:
                    crm.save_enrichment(opportunity, deps.enricher.enrich(domain))
                    crm.add_log(opportunity, "enriched", "ok", f"Fetched {domain}")
                except EnrichmentError as exc:
                    crm.add_log(opportunity, "enriched", "failed", f"{domain}: {exc}")

        # 2. LLM extraction and 3. validation. Stored only once both pass.
        step = "extracted"
        if opportunity.extracted is None:
            try:
                extracted = deps.llm.extract(text, opportunity.enrichment)
            except ExtractionError as exc:
                raise StepFailure("extracted", str(exc)) from exc
            crm.add_log(opportunity, "extracted", "ok")

            step = "validated"
            validate_extraction(extracted)
            extracted.domain = normalize_domain(extracted.domain) or first_domain(text)
            crm.save_extraction(opportunity, extracted.model_dump())
            crm.add_log(opportunity, "validated", "ok")
        else:
            extracted = ExtractedCompany.model_validate(opportunity.extracted)
            crm.add_log(opportunity, "extracted", "skipped", "Reusing stored extraction")
            crm.add_log(opportunity, "validated", "skipped", "Reusing stored extraction")

        # 4. Screening. A short follow-up ("we closed our round") is judged together with
        # what the CRM already knows about that company, not in isolation.
        step = "screened"
        known = crm.find_company(extracted.domain, extracted.company_name)
        effective, filled = _fill_gaps(extracted, known)
        result = screen(effective, deps.thesis)
        note = " (gaps filled from the existing company record)" if filled else ""
        crm.add_log(opportunity, "screened", "ok", f"Verdict: {result.verdict}{note}")

        # 5. Deduplicate + write to the CRM
        step = "saved"
        company, created = crm.assert_company(
            CompanyData(
                name=extracted.company_name or "",
                domain=extracted.domain,
                website=f"https://{extracted.domain}" if extracted.domain else None,
                location=extracted.location,
                country=extracted.country,
                industry=extracted.industry,
                product=extracted.product,
                funding_stage=extracted.funding_stage,
                description=extracted.description,
            )
        )
        crm.complete_opportunity(opportunity, company, result)
        crm.add_log(
            opportunity, "saved", "ok", f"{'Created' if created else 'Updated'} company {company.name}"
        )
    except StepFailure as failure:
        crm.fail_opportunity(opportunity, failure.step, failure.message)
    except Exception as exc:  # noqa: BLE001 - keep the pitch, record the failure
        logger.exception("Unexpected error in step %r for opportunity %s", step, opportunity.id)
        crm.fail_opportunity(opportunity, step, f"Unexpected error ({type(exc).__name__})")
