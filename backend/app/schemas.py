from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FundingStage = Literal[
    "pre-seed", "seed", "series-a", "series-b", "series-c-plus", "growth", "unknown"
]
FUNDING_STAGES: tuple[str, ...] = (
    "pre-seed", "seed", "series-a", "series-b", "series-c-plus", "growth", "unknown",
)  # fmt: skip
ReviewStatus = Literal["new", "in_review", "passed", "rejected"]
Verdict = Literal["pass", "maybe", "fail"]


# ---------- pipeline models ----------


class PitchIn(BaseModel):
    source: str = Field(default="manual", min_length=1, max_length=50)
    sender: str | None = Field(default=None, max_length=320)
    subject: str | None = Field(default=None, max_length=300)
    body: str = Field(max_length=20000)
    received_at: datetime | None = None

    @field_validator("body")
    @classmethod
    def body_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Pitch body must not be empty")
        return value

    @field_validator("sender", "subject")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()


class ExtractedCompany(BaseModel):
    """What the LLM must return. Unknown values are null, never guessed."""

    company_name: str | None = None
    domain: str | None = None
    founders: list[str] = Field(default_factory=list)
    location: str | None = None
    country: str | None = None
    industry: str | None = None
    product: str | None = None
    funding_stage: FundingStage | None = None
    funding_amount: str | None = None
    description: str | None = None


class ScreeningResult(BaseModel):
    verdict: Verdict
    reasons: list[str]
    criteria_matched: list[str]


class CompanyData(BaseModel):
    """Input for a company upsert."""

    name: str = Field(min_length=1, max_length=300)
    domain: str | None = None
    website: str | None = None
    location: str | None = None
    country: str | None = None
    industry: str | None = None
    product: str | None = None
    funding_stage: str | None = None
    description: str | None = None


# ---------- API models ----------


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    domain: str | None
    website: str | None
    location: str | None
    country: str | None
    industry: str | None
    product: str | None
    funding_stage: str | None
    description: str | None
    needs_review: bool
    opportunity_count: int = 0
    created_at: datetime
    updated_at: datetime


class AssertCompanyResult(BaseModel):
    created: bool
    company: CompanyOut


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step: str
    status: str
    message: str | None
    created_at: datetime


class OpportunityListItem(BaseModel):
    id: int
    company_id: int | None
    company_name: str | None
    company_domain: str | None
    location: str | None
    funding_stage: str | None
    verdict: str | None
    status: str
    processing_state: str
    failed_step: str | None
    error: str | None
    source: str
    sender: str | None
    subject: str | None
    received_at: datetime
    created_at: datetime


class OpportunityDetail(OpportunityListItem):
    raw_body: str
    extracted: dict | None
    enrichment: dict | None
    screening_reasons: list[str]
    criteria_matched: list[str]
    company: CompanyOut | None
    logs: list[LogOut]


class SubmitResult(BaseModel):
    created: bool
    opportunity: OpportunityDetail


class StatusUpdate(BaseModel):
    status: ReviewStatus


class SamplePitch(BaseModel):
    id: str
    label: str
    pitch: PitchIn
