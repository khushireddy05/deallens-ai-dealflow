from app.enrichment.base import EnrichmentError
from app.llm.base import ExtractionError
from app.schemas import ExtractedCompany


class FakeEnricher:
    def __init__(self, result: dict | None = None, error: str | None = None):
        self.result = result or {
            "domain": "example.test",
            "url": "https://example.test/",
            "title": "Example",
            "description": "An example company",
            "text_excerpt": "We build things.",
        }
        self.error = error
        self.calls: list[str] = []

    def enrich(self, domain: str) -> dict:
        self.calls.append(domain)
        if self.error:
            raise EnrichmentError(self.error)
        return self.result


class CountingLLM:
    """Wraps another extractor and counts calls; can fail the first N calls."""

    def __init__(self, inner, fail_first: int = 0):
        self.inner = inner
        self.fail_first = fail_first
        self.calls = 0

    def extract(self, pitch_text: str, enrichment: dict | None) -> ExtractedCompany:
        self.calls += 1
        if self.calls <= self.fail_first:
            raise ExtractionError("simulated LLM outage")
        return self.inner.extract(pitch_text, enrichment)


class StaticLLM:
    def __init__(self, extracted: ExtractedCompany):
        self.extracted = extracted

    def extract(self, pitch_text: str, enrichment: dict | None) -> ExtractedCompany:
        return self.extracted.model_copy(deep=True)


class FlakyCRM:
    """Delegates to a real CRM but fails `assert_company` the first N times."""

    def __init__(self, inner, fail_assert_times: int = 1):
        self._inner = inner
        self.fail_assert_times = fail_assert_times
        self.assert_calls = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def assert_company(self, data):
        self.assert_calls += 1
        if self.assert_calls <= self.fail_assert_times:
            raise RuntimeError("simulated CRM outage")
        return self._inner.assert_company(data)
