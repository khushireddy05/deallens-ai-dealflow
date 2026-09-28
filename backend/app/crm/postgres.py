from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..models import Company, Opportunity, ProcessingLog, utcnow
from ..normalize import normalize_domain, normalize_name
from ..schemas import CompanyData, PitchIn, ScreeningResult

# Company fields that a later pitch may fill in or refresh (never blank out).
_MERGE_FIELDS = (
    "website", "location", "country", "industry", "product", "funding_stage", "description",
)  # fmt: skip


class PostgresCRM:
    """CRM backed by the app database. Every write method commits, so each pipeline step
    survives a later failure."""

    def __init__(self, session: Session):
        self.session = session

    # ---------- companies ----------

    def find_company_by_domain(self, domain: str) -> Company | None:
        return self.session.scalar(select(Company).where(Company.domain == domain))

    def _find_company_by_name(self, normalized_name: str) -> Company | None:
        return self.session.scalar(
            select(Company)
            .where(Company.normalized_name == normalized_name)
            .order_by(Company.id)
            .limit(1)
        )

    def _match_company(
        self, domain: str | None, normalized_name: str
    ) -> tuple[Company | None, bool]:
        """The dedup rule. Returns (existing company or None, matched_by_name_only)."""
        if domain:
            company = self.find_company_by_domain(domain)
            if company is None and normalized_name:
                # Adopt an earlier record for the same name that had no domain yet.
                candidate = self._find_company_by_name(normalized_name)
                if candidate is not None and candidate.domain is None:
                    company = candidate
            return company, False
        if normalized_name:
            company = self._find_company_by_name(normalized_name)
            return company, company is not None
        return None, False

    def find_company(self, domain: str | None, name: str | None) -> Company | None:
        """Read-only lookup using the same matching rule as `assert_company`."""
        return self._match_company(normalize_domain(domain), normalize_name(name))[0]

    def assert_company(self, data: CompanyData) -> tuple[Company, bool]:
        """Upsert. Match by domain; without a domain, by exact normalized name.

        A name-only match is flagged `needs_review` so a human can confirm the merge.
        """
        domain = normalize_domain(data.domain)
        normalized = normalize_name(data.name)
        company, matched_by_name_only = self._match_company(domain, normalized)

        if company is None:
            company = Company(
                name=data.name.strip(),
                normalized_name=normalized,
                domain=domain,
                needs_review=domain is None,
            )
            for field in _MERGE_FIELDS:
                setattr(company, field, getattr(data, field))
            try:
                with self.session.begin_nested():
                    self.session.add(company)
                    self.session.flush()
            except IntegrityError:
                # Another request created the same domain first: use theirs.
                existing = self.find_company_by_domain(domain) if domain else None
                if existing is None:
                    raise
                return self._merge(existing, data, domain, matched_by_name_only), False
            self.session.commit()
            return company, True

        return self._merge(company, data, domain, matched_by_name_only), False

    def _merge(
        self, company: Company, data: CompanyData, domain: str | None, by_name_only: bool
    ) -> Company:
        for field in _MERGE_FIELDS:
            value = getattr(data, field)
            # A missing (or "unknown") value never overwrites what we already know.
            if value and value != "unknown":
                setattr(company, field, value)
        if domain and company.domain is None:
            company.domain = domain
            company.needs_review = False
        if by_name_only:
            company.needs_review = True
        self.session.commit()
        return company

    def list_companies(self, q: str | None = None, domain: str | None = None):
        stmt = (
            select(Company, func.count(Opportunity.id))
            .outerjoin(Opportunity, Opportunity.company_id == Company.id)
            .group_by(Company.id)
            .order_by(Company.name)
        )
        if domain:
            stmt = stmt.where(Company.domain == normalize_domain(domain))
        if q:
            stmt = stmt.where(
                or_(
                    func.lower(Company.name).contains(q.lower(), autoescape=True),
                    func.lower(func.coalesce(Company.domain, "")).contains(
                        q.lower(), autoescape=True
                    ),
                )
            )
        return self.session.execute(stmt).all()

    def count_company_opportunities(self, company_id: int) -> int:
        return (
            self.session.scalar(
                select(func.count(Opportunity.id)).where(Opportunity.company_id == company_id)
            )
            or 0
        )

    # ---------- opportunities ----------

    def get_opportunity(self, opportunity_id: int) -> Opportunity | None:
        return self.session.get(Opportunity, opportunity_id)

    def get_opportunity_by_key(self, key: str) -> Opportunity | None:
        return self.session.scalar(select(Opportunity).where(Opportunity.idempotency_key == key))

    def create_opportunity(self, pitch: PitchIn, key: str) -> tuple[Opportunity, bool]:
        existing = self.get_opportunity_by_key(key)
        if existing is not None:
            return existing, False
        opportunity = Opportunity(
            source=pitch.source,
            sender=pitch.sender,
            subject=pitch.subject,
            raw_body=pitch.body,
            received_at=pitch.received_at or utcnow(),
            idempotency_key=key,
            status="new",
            processing_state="pending",
        )
        try:
            with self.session.begin_nested():
                self.session.add(opportunity)
                self.session.flush()
        except IntegrityError:
            existing = self.get_opportunity_by_key(key)
            if existing is None:
                raise
            return existing, False
        self.session.commit()
        return opportunity, True

    def list_opportunities(
        self,
        verdict: str | None = None,
        status: str | None = None,
        processing_state: str | None = None,
        q: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Opportunity]:
        stmt = (
            select(Opportunity)
            .outerjoin(Company, Company.id == Opportunity.company_id)
            .options(joinedload(Opportunity.company))
            .order_by(Opportunity.created_at.desc(), Opportunity.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if verdict:
            stmt = stmt.where(Opportunity.verdict == verdict)
        if status:
            stmt = stmt.where(Opportunity.status == status)
        if processing_state:
            stmt = stmt.where(Opportunity.processing_state == processing_state)
        if q:
            needle = q.lower()
            stmt = stmt.where(
                or_(
                    func.lower(func.coalesce(Company.name, "")).contains(needle, autoescape=True),
                    func.lower(func.coalesce(Opportunity.subject, "")).contains(
                        needle, autoescape=True
                    ),
                    func.lower(func.coalesce(Opportunity.sender, "")).contains(
                        needle, autoescape=True
                    ),
                )
            )
        return list(self.session.scalars(stmt).unique())

    def set_status(self, opportunity: Opportunity, status: str) -> None:
        opportunity.status = status
        self.session.commit()

    # ---------- pipeline state ----------

    def add_log(
        self, opportunity: Opportunity, step: str, status: str, message: str | None = None
    ) -> None:
        self.session.add(
            ProcessingLog(
                opportunity_id=opportunity.id, step=step, status=status, message=message
            )
        )
        self.session.commit()

    def mark_processing(self, opportunity: Opportunity) -> None:
        opportunity.processing_state = "processing"
        opportunity.error = None
        opportunity.failed_step = None
        self.session.commit()

    def save_enrichment(self, opportunity: Opportunity, enrichment: dict) -> None:
        opportunity.enrichment = enrichment
        self.session.commit()

    def save_extraction(self, opportunity: Opportunity, extracted: dict) -> None:
        opportunity.extracted = extracted
        self.session.commit()

    def complete_opportunity(
        self, opportunity: Opportunity, company: Company, result: ScreeningResult
    ) -> None:
        opportunity.company_id = company.id
        opportunity.verdict = result.verdict
        opportunity.screening_reasons = result.reasons
        opportunity.criteria_matched = result.criteria_matched
        opportunity.processing_state = "completed"
        opportunity.error = None
        opportunity.failed_step = None
        self.session.commit()

    def fail_opportunity(self, opportunity: Opportunity, step: str, message: str) -> None:
        # Drop any half-finished transaction first; the raw pitch is already committed.
        self.session.rollback()
        opportunity.processing_state = "failed"
        opportunity.failed_step = step
        opportunity.error = message
        self.session.add(
            ProcessingLog(
                opportunity_id=opportunity.id, step=step, status="failed", message=message
            )
        )
        self.session.commit()
