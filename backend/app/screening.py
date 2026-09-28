import json
import re
from dataclasses import dataclass
from pathlib import Path

from .schemas import ExtractedCompany, ScreeningResult


@dataclass(frozen=True)
class Thesis:
    name: str
    ai_keywords: tuple[str, ...]
    countries: frozenset[str]
    stages: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "ai_keywords": list(self.ai_keywords),
            "countries": sorted(self.countries),
            "stages": list(self.stages),
        }


def load_thesis(path: Path) -> Thesis:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Thesis(
        name=data["name"],
        ai_keywords=tuple(k.lower() for k in data["ai_keywords"]),
        countries=frozenset(c.strip().lower() for c in data["countries"]),
        stages=tuple(data["stages"]),
    )


# Outcome of one criterion: matched, mismatched, or not enough information.
MATCH, MISMATCH, UNKNOWN = "match", "mismatch", "unknown"


def _check_ai(company: ExtractedCompany, thesis: Thesis) -> tuple[str, str]:
    text = " ".join(filter(None, (company.industry, company.product, company.description)))
    if not text.strip():
        return UNKNOWN, "Cannot tell if it is AI-related: no industry, product or description"
    lowered = text.lower()
    for keyword in thesis.ai_keywords:
        # Word boundaries so "ai" does not match "maintain" or "email".
        if re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", lowered):
            return MATCH, f"AI-related (mentions '{keyword}')"
    return MISMATCH, "Not AI-related: no AI terms in industry, product or description"


def _check_geography(company: ExtractedCompany, thesis: Thesis) -> tuple[str, str]:
    country = (company.country or "").strip().lower()
    if not country:
        return UNKNOWN, "Country unknown"
    if country in thesis.countries:
        return MATCH, f"In thesis geography ({company.country})"
    return MISMATCH, f"Outside thesis geography ({company.country})"


def _check_stage(company: ExtractedCompany, thesis: Thesis) -> tuple[str, str]:
    stage = company.funding_stage
    if stage is None or stage == "unknown":
        return UNKNOWN, "Funding stage unknown"
    if stage in thesis.stages:
        return MATCH, f"In thesis stage range ({stage})"
    return MISMATCH, f"Outside thesis stage range ({stage})"


def screen(company: ExtractedCompany, thesis: Thesis) -> ScreeningResult:
    """Rule-based first-pass screening. Any mismatch fails; missing data gives 'maybe'."""
    checks = {
        "ai": _check_ai(company, thesis),
        "geography": _check_geography(company, thesis),
        "stage": _check_stage(company, thesis),
    }
    outcomes = [outcome for outcome, _ in checks.values()]
    if MISMATCH in outcomes:
        verdict = "fail"
    elif UNKNOWN in outcomes:
        verdict = "maybe"
    else:
        verdict = "pass"
    return ScreeningResult(
        verdict=verdict,
        reasons=[reason for _, reason in checks.values()],
        criteria_matched=[name for name, (outcome, _) in checks.items() if outcome == MATCH],
    )
