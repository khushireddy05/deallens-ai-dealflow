from app.schemas import ExtractedCompany
from app.screening import screen


def company(**overrides) -> ExtractedCompany:
    base = dict(
        company_name="X",
        country="Germany",
        industry="Industrial AI",
        product="AI software",
        funding_stage="seed",
        description="Builds things.",
    )
    base.update(overrides)
    return ExtractedCompany(**base)


def test_all_criteria_match_passes(thesis):
    result = screen(company(), thesis)
    assert result.verdict == "pass"
    assert result.criteria_matched == ["ai", "geography", "stage"]
    assert len(result.reasons) == 3


def test_outside_geography_fails(thesis):
    result = screen(company(country="United States"), thesis)
    assert result.verdict == "fail"
    assert "geography" not in result.criteria_matched
    assert any("Outside thesis geography" in r for r in result.reasons)


def test_outside_stage_fails(thesis):
    result = screen(company(funding_stage="series-b"), thesis)
    assert result.verdict == "fail"
    assert any("Outside thesis stage range" in r for r in result.reasons)


def test_not_ai_fails(thesis):
    result = screen(
        company(industry="Bakery", product="Bread", description="Sells bread in Vienna."), thesis
    )
    assert result.verdict == "fail"
    assert "ai" not in result.criteria_matched


def test_missing_information_gives_maybe_not_fail(thesis):
    result = screen(company(country=None, funding_stage=None), thesis)
    assert result.verdict == "maybe"
    assert result.criteria_matched == ["ai"]


def test_unknown_stage_value_is_treated_as_missing(thesis):
    assert screen(company(funding_stage="unknown"), thesis).verdict == "maybe"


def test_a_mismatch_beats_missing_data(thesis):
    result = screen(company(country="United States", funding_stage=None), thesis)
    assert result.verdict == "fail"


def test_no_text_at_all_is_unknown_for_ai(thesis):
    result = screen(company(industry=None, product=None, description=None), thesis)
    assert result.verdict == "maybe"
    assert "ai" not in result.criteria_matched


def test_ai_keyword_needs_word_boundaries(thesis):
    # "maintain", "email" and "paid" contain the letters "ai" but are not AI.
    result = screen(
        company(industry="Facility", product="We maintain email and paid tools", description=None),
        thesis,
    )
    assert result.verdict == "fail"


def test_ai_keyword_matches_with_punctuation(thesis):
    result = screen(company(industry="Retail", product="AI-powered checkout", description=None), thesis)
    assert "ai" in result.criteria_matched


def test_country_matching_is_case_insensitive(thesis):
    assert "geography" in screen(company(country="  GERMANY "), thesis).criteria_matched
