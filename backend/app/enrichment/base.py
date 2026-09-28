from typing import Protocol


class EnrichmentError(Exception):
    """Enrichment could not fetch or parse anything. Never fatal to the pipeline."""


class EnrichmentProvider(Protocol):
    def enrich(self, domain: str) -> dict:
        """Return public facts about the company at `domain`.

        Raises EnrichmentError on any failure.
        """
