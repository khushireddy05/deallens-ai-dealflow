from typing import Protocol

from ..schemas import ExtractedCompany


class ExtractionError(Exception):
    """The LLM step could not produce valid structured data."""


class LLMClient(Protocol):
    def extract(self, pitch_text: str, enrichment: dict | None) -> ExtractedCompany:
        """Turn pitch text (plus optional website info) into structured fields.

        Must raise ExtractionError if no valid result could be produced.
        """
