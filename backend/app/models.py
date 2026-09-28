from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# JSONB on Postgres, plain JSON elsewhere (the tests can run on SQLite).
JSONType = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    normalized_name: Mapped[str] = mapped_column(String(300), index=True, default="")
    # Unique for dedup. NULL is allowed (several companies may have no known domain).
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product: Mapped[str | None] = mapped_column(Text, nullable=True)
    funding_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="company")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(50))
    sender: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    raw_body: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    enrichment: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    extracted: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    # Automated result. Kept separate from the human decision in `status` (FR-28).
    verdict: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    screening_reasons: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    criteria_matched: Mapped[list | None] = mapped_column(JSONType, nullable=True)

    # Human review status: new / in_review / passed / rejected.
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)

    # Pipeline state: pending / processing / completed / failed.
    processing_state: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    failed_step: Mapped[str | None] = mapped_column(String(30), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Unique so the same pitch can never be stored twice (FR-21).
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    company: Mapped[Company | None] = relationship(back_populates="opportunities")
    logs: Mapped[list["ProcessingLog"]] = relationship(
        back_populates="opportunity",
        order_by="ProcessingLog.id",
        cascade="all, delete-orphan",
    )


class ProcessingLog(Base):
    __tablename__ = "processing_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"), index=True
    )
    step: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(10))  # ok / failed / skipped
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    opportunity: Mapped[Opportunity] = relationship(back_populates="logs")
