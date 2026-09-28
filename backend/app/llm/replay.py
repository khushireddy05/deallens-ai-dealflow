"""A no-network 'LLM' that replays recorded extractions for the bundled sample pitches.

Used for demo mode (LLM_PROVIDER=replay), for seeding, and as the fake LLM in tests.
"""

import json
import re
from pathlib import Path

from ..normalize import build_pitch_text
from ..schemas import ExtractedCompany
from .base import ExtractionError


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


class ReplayExtractor:
    def __init__(self, samples: list[dict]):
        self._by_text: dict[str, dict | None] = {}
        for sample in samples:
            pitch = sample["pitch"]
            text = build_pitch_text(pitch.get("subject"), pitch["body"])
            self._by_text[_key(text)] = sample.get("extraction")

    @classmethod
    def from_file(cls, path: Path) -> "ReplayExtractor":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def extract(self, pitch_text: str, enrichment: dict | None) -> ExtractedCompany:
        key = _key(pitch_text)
        if key not in self._by_text:
            raise ExtractionError(
                "Demo mode (LLM_PROVIDER=replay) only recognises the bundled sample pitches. "
                "Set LLM_PROVIDER=openai and an API key to process other text."
            )
        recorded = self._by_text[key]
        if recorded is None:
            # Simulates a model that returned nothing usable.
            raise ExtractionError("Model output was not valid structured data")
        return ExtractedCompany.model_validate(recorded)
