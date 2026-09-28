from .models import Company, Opportunity
from .schemas import CompanyOut, LogOut, OpportunityDetail, OpportunityListItem


def company_out(company: Company, opportunity_count: int = 0) -> CompanyOut:
    out = CompanyOut.model_validate(company)
    out.opportunity_count = opportunity_count
    return out


def _known_stage(stage: str | None) -> str | None:
    return None if stage in (None, "", "unknown") else stage


def _list_fields(opp: Opportunity) -> dict:
    extracted = opp.extracted or {}
    company = opp.company
    return {
        "id": opp.id,
        "company_id": opp.company_id,
        "company_name": company.name if company else extracted.get("company_name"),
        "company_domain": company.domain if company else extracted.get("domain"),
        # What the pitch said, else what the CRM knows about the company.
        "location": extracted.get("location") or (company.location if company else None),
        "funding_stage": _known_stage(extracted.get("funding_stage"))
        or (_known_stage(company.funding_stage) if company else None),
        "verdict": opp.verdict,
        "status": opp.status,
        "processing_state": opp.processing_state,
        "failed_step": opp.failed_step,
        "error": opp.error,
        "source": opp.source,
        "sender": opp.sender,
        "subject": opp.subject,
        "received_at": opp.received_at,
        "created_at": opp.created_at,
    }


def opportunity_list_item(opp: Opportunity) -> OpportunityListItem:
    return OpportunityListItem(**_list_fields(opp))


def opportunity_detail(opp: Opportunity, company_opportunity_count: int = 0) -> OpportunityDetail:
    return OpportunityDetail(
        **_list_fields(opp),
        raw_body=opp.raw_body,
        extracted=opp.extracted,
        enrichment=opp.enrichment,
        screening_reasons=opp.screening_reasons or [],
        criteria_matched=opp.criteria_matched or [],
        company=company_out(opp.company, company_opportunity_count) if opp.company else None,
        logs=[LogOut.model_validate(log) for log in opp.logs],
    )
