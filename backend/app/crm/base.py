from typing import Protocol

from ..models import Company, Opportunity
from ..schemas import CompanyData, PitchIn, ScreeningResult


class CRMClient(Protocol):
    """What the pipeline needs from a CRM.

    `PostgresCRM` is the v1 implementation. A different backend (for example Attio) only has
    to provide these methods; the pipeline does not change.
    """

    def get_opportunity(self, opportunity_id: int) -> Opportunity | None: ...

    def get_opportunity_by_key(self, key: str) -> Opportunity | None: ...

    def create_opportunity(self, pitch: PitchIn, key: str) -> tuple[Opportunity, bool]:
        """Store the raw pitch. Returns (opportunity, created). Same key -> existing row."""

    def add_log(
        self, opportunity: Opportunity, step: str, status: str, message: str | None = None
    ) -> None: ...

    def mark_processing(self, opportunity: Opportunity) -> None: ...

    def save_enrichment(self, opportunity: Opportunity, enrichment: dict) -> None: ...

    def save_extraction(self, opportunity: Opportunity, extracted: dict) -> None: ...

    def find_company(self, domain: str | None, name: str | None) -> Company | None:
        """Read-only: the existing company a pitch would be merged into, if any."""

    def assert_company(self, data: CompanyData) -> tuple[Company, bool]:
        """Create or update a company. Returns (company, created)."""

    def complete_opportunity(
        self, opportunity: Opportunity, company: Company, result: ScreeningResult
    ) -> None: ...

    def fail_opportunity(self, opportunity: Opportunity, step: str, message: str) -> None: ...
