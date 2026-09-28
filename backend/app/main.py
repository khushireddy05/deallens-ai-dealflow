import json
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .crm.postgres import PostgresCRM
from .db import get_sessionmaker, init_db
from .deps import get_crm, get_pipeline, get_thesis
from .pipeline import (
    NotRetryable,
    OpportunityNotFound,
    PipelineDeps,
    retry_opportunity,
    submit_pitch,
)
from .schemas import (
    AssertCompanyResult,
    CompanyData,
    CompanyOut,
    OpportunityDetail,
    OpportunityListItem,
    PitchIn,
    SamplePitch,
    StatusUpdate,
    SubmitResult,
)
from .screening import Thesis
from .seed import seed_if_empty
from .serializers import company_out, opportunity_detail, opportunity_list_item


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if get_settings().seed_on_start:
        with get_sessionmaker()() as session:
            seed_if_empty(session)
    yield


app = FastAPI(
    title="DealLens",
    version="0.1.0",
    description="CRM-style API plus the AI triage pipeline for inbound startup pitches.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Content-Type"],
)


def _get_opportunity_or_404(crm: PostgresCRM, opportunity_id: int):
    opportunity = crm.get_opportunity(opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opportunity


def _detail(crm: PostgresCRM, opportunity) -> OpportunityDetail:
    count = crm.count_company_opportunities(opportunity.company_id) if opportunity.company_id else 0
    return opportunity_detail(opportunity, count)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/thesis")
def get_thesis_config(thesis: Thesis = Depends(get_thesis)):
    return thesis.as_dict()


@app.get("/samples", response_model=list[SamplePitch])
def samples():
    path = get_settings().samples_path
    items = json.loads(path.read_text(encoding="utf-8"))
    return [{"id": s["id"], "label": s["label"], "pitch": s["pitch"]} for s in items]


# ---------- companies ----------


@app.get("/companies", response_model=list[CompanyOut])
def list_companies(
    q: str | None = Query(default=None, max_length=100),
    domain: str | None = Query(default=None, max_length=255),
    crm: PostgresCRM = Depends(get_crm),
):
    return [company_out(company, count) for company, count in crm.list_companies(q, domain)]


@app.put("/companies/assert", response_model=AssertCompanyResult)
def assert_company(data: CompanyData, crm: PostgresCRM = Depends(get_crm)):
    company, created = crm.assert_company(data)
    return AssertCompanyResult(
        created=created,
        company=company_out(company, crm.count_company_opportunities(company.id)),
    )


# ---------- opportunities ----------


@app.get("/opportunities", response_model=list[OpportunityListItem])
def list_opportunities(
    verdict: Literal["pass", "maybe", "fail"] | None = None,
    status: Literal["new", "in_review", "passed", "rejected"] | None = None,
    processing_state: Literal["pending", "processing", "completed", "failed"] | None = None,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    crm: PostgresCRM = Depends(get_crm),
):
    rows = crm.list_opportunities(verdict, status, processing_state, q, limit, offset)
    return [opportunity_list_item(row) for row in rows]


@app.post("/opportunities", response_model=SubmitResult)
def create_opportunity(
    pitch: PitchIn, response: Response, deps: PipelineDeps = Depends(get_pipeline)
):
    """Submit a pitch and run the pipeline. Resubmitting identical text is a no-op (200)."""
    opportunity, created = submit_pitch(deps, pitch)
    response.status_code = 201 if created else 200
    return SubmitResult(created=created, opportunity=_detail(deps.crm, opportunity))


@app.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(opportunity_id: int, crm: PostgresCRM = Depends(get_crm)):
    return _detail(crm, _get_opportunity_or_404(crm, opportunity_id))


@app.patch("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
def update_status(
    opportunity_id: int, update: StatusUpdate, crm: PostgresCRM = Depends(get_crm)
):
    """Human review. Only the status changes; the automated verdict is left alone."""
    opportunity = _get_opportunity_or_404(crm, opportunity_id)
    crm.set_status(opportunity, update.status)
    return _detail(crm, opportunity)


@app.post("/opportunities/{opportunity_id}/retry", response_model=OpportunityDetail)
def retry(opportunity_id: int, deps: PipelineDeps = Depends(get_pipeline)):
    try:
        opportunity = retry_opportunity(deps, opportunity_id)
    except OpportunityNotFound:
        raise HTTPException(status_code=404, detail="Opportunity not found") from None
    except NotRetryable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return _detail(deps.crm, opportunity)


@app.get("/failures", response_model=list[OpportunityListItem])
def list_failures(crm: PostgresCRM = Depends(get_crm)):
    rows = crm.list_opportunities(processing_state="failed", limit=500)
    return [opportunity_list_item(row) for row in rows]
