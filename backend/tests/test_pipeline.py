import pytest

from app.models import Company, Opportunity
from app.pipeline import (
    NotRetryable,
    OpportunityNotFound,
    PipelineDeps,
    retry_opportunity,
    submit_pitch,
)
from app.schemas import ExtractedCompany, PitchIn

from .fakes import CountingLLM, FakeEnricher, FlakyCRM, StaticLLM


def pitch_of(samples, sample_id) -> PitchIn:
    return PitchIn(**samples[sample_id]["pitch"])


def steps(opportunity) -> list[tuple[str, str]]:
    return [(log.step, log.status) for log in opportunity.logs]


def count(session, model) -> int:
    return session.query(model).count()


# ---------- happy path ----------


def test_happy_path_creates_company_and_opportunity(deps, samples, session):
    opportunity, created = submit_pitch(deps, pitch_of(samples, "clean-abc-ai"))

    assert created is True
    assert opportunity.processing_state == "completed"
    assert opportunity.verdict == "pass"
    assert opportunity.status == "new"
    assert opportunity.company.name == "ABC AI"
    assert opportunity.company.domain == "abc-ai.example"
    assert opportunity.extracted["country"] == "Germany"
    assert opportunity.screening_reasons and opportunity.criteria_matched == ["ai", "geography", "stage"]
    assert steps(opportunity) == [
        ("received", "ok"),
        ("enriched", "skipped"),
        ("extracted", "ok"),
        ("validated", "ok"),
        ("screened", "ok"),
        ("saved", "ok"),
    ]
    assert count(session, Company) == 1


# ---------- idempotency (FR-21) ----------


def test_submitting_the_same_pitch_twice_creates_nothing_new(deps, samples, session):
    llm = CountingLLM(deps.llm)
    deps = PipelineDeps(deps.crm, llm, None, deps.thesis)

    first, created_first = submit_pitch(deps, pitch_of(samples, "clean-abc-ai"))
    second, created_second = submit_pitch(deps, pitch_of(samples, "clean-abc-ai"))

    assert (created_first, created_second) == (True, False)
    assert first.id == second.id
    assert count(session, Opportunity) == 1
    assert count(session, Company) == 1
    assert llm.calls == 1  # the second submit did no work at all


def test_whitespace_and_case_changes_are_still_the_same_pitch(deps, samples, session):
    original = pitch_of(samples, "clean-abc-ai")
    reformatted = original.model_copy(
        update={"body": original.body.upper().replace("\n", "  \n "), "sender": original.sender.upper()}
    )
    submit_pitch(deps, original)
    # The replay LLM would not know the reformatted text; idempotency must stop it getting that far.
    _, created = submit_pitch(deps, reformatted)
    assert created is False
    assert count(session, Opportunity) == 1


# ---------- dedup (FR-17..20) ----------


def test_same_company_twice_gives_one_company_two_opportunities(deps, samples, session):
    first, _ = submit_pitch(deps, pitch_of(samples, "clean-abc-ai"))
    second, created = submit_pitch(deps, pitch_of(samples, "abc-ai-followup"))

    assert created is True
    assert first.company_id == second.company_id
    assert count(session, Company) == 1
    assert count(session, Opportunity) == 2
    # the follow-up had no location; the earlier value must survive the update
    assert second.company.location == "Berlin"
    assert second.company.funding_stage == "seed"


def test_follow_up_is_screened_together_with_the_known_company(deps, samples):
    """The follow-up email has no location. On its own that would be 'maybe'."""
    submit_pitch(deps, pitch_of(samples, "clean-abc-ai"))
    second, _ = submit_pitch(deps, pitch_of(samples, "abc-ai-followup"))

    assert second.extracted["country"] is None  # what the pitch itself said
    assert second.verdict == "pass"
    assert "In thesis geography (Germany)" in second.screening_reasons[1]
    screened = next(log for log in second.logs if log.step == "screened")
    assert "existing company record" in screened.message


def test_same_follow_up_without_history_is_only_a_maybe(deps, samples):
    opportunity, _ = submit_pitch(deps, pitch_of(samples, "abc-ai-followup"))
    assert opportunity.verdict == "maybe"


def test_unknown_stage_never_overwrites_a_known_stage(deps, samples):
    from app.schemas import CompanyData

    deps.crm.assert_company(CompanyData(name="X", domain="x.example", funding_stage="seed"))
    company, _ = deps.crm.assert_company(CompanyData(name="X", domain="x.example", funding_stage="unknown"))
    assert company.funding_stage == "seed"


def test_pitch_without_website_creates_company_flagged_for_review(deps, samples):
    opportunity, _ = submit_pitch(deps, pitch_of(samples, "no-website-startup"))
    assert opportunity.processing_state == "completed"
    assert opportunity.company.domain is None
    assert opportunity.company.needs_review is True


# ---------- screening outcomes ----------


@pytest.mark.parametrize("sample_id", ["non-ai-europe", "ambiguous-stage", "prompt-injection", "seed-atlas-robotics"])
def test_screening_verdicts(deps, samples, sample_id):
    opportunity, _ = submit_pitch(deps, pitch_of(samples, sample_id))
    assert opportunity.verdict == samples[sample_id]["expected"]["verdict"]
    assert opportunity.processing_state == "completed"


def test_prompt_injection_cannot_change_the_verdict(deps, samples):
    opportunity, _ = submit_pitch(deps, pitch_of(samples, "prompt-injection"))
    assert opportunity.verdict == "fail"
    assert opportunity.status == "new"


# ---------- failures ----------


def test_invalid_llm_output_fails_cleanly_and_writes_nothing(deps, samples, session):
    opportunity, _ = submit_pitch(deps, pitch_of(samples, "garbage"))

    assert opportunity.processing_state == "failed"
    assert opportunity.failed_step == "extracted"
    assert "not valid structured data" in opportunity.error
    assert opportunity.company_id is None and opportunity.verdict is None
    assert count(session, Company) == 0
    assert ("extracted", "failed") in steps(opportunity)
    assert opportunity.raw_body  # the pitch itself is never lost


def test_missing_required_field_fails_validation(deps, samples, session):
    opportunity, _ = submit_pitch(deps, pitch_of(samples, "missing-name"))
    assert opportunity.processing_state == "failed"
    assert opportunity.failed_step == "validated"
    assert "company_name" in opportunity.error
    assert opportunity.extracted is None  # invalid output is not stored
    assert count(session, Company) == 0


def test_description_or_product_is_required(deps, session):
    llm = StaticLLM(ExtractedCompany(company_name="Empty Co"))
    opportunity, _ = submit_pitch(PipelineDeps(deps.crm, llm, None, deps.thesis), PitchIn(body="x"))
    assert opportunity.processing_state == "failed"
    assert "description or product" in opportunity.error


def test_unexpected_exception_is_recorded_not_raised(deps, samples, session):
    crm = FlakyCRM(deps.crm, fail_assert_times=1)
    opportunity, _ = submit_pitch(PipelineDeps(crm, deps.llm, None, deps.thesis), pitch_of(samples, "clean-abc-ai"))
    assert opportunity.processing_state == "failed"
    assert opportunity.failed_step == "saved"
    assert "RuntimeError" in opportunity.error
    assert "simulated" not in opportunity.error  # internal details are not exposed
    assert count(session, Company) == 0


# ---------- enrichment (FR-4..6) ----------


def test_enrichment_result_is_stored_and_passed_to_the_llm(deps, samples):
    enricher = FakeEnricher()
    seen = {}

    class SpyLLM:
        def extract(self, text, enrichment):
            seen["enrichment"] = enrichment
            return deps.llm.extract(text, enrichment)

    opportunity, _ = submit_pitch(
        PipelineDeps(deps.crm, SpyLLM(), enricher, deps.thesis), pitch_of(samples, "clean-abc-ai")
    )
    assert enricher.calls == ["abc-ai.example"]
    assert opportunity.enrichment["title"] == "Example"
    assert seen["enrichment"]["title"] == "Example"
    assert ("enriched", "ok") in steps(opportunity)


def test_enrichment_failure_does_not_stop_processing(deps, samples):
    enricher = FakeEnricher(error="DNS lookup failed for abc-ai.example")
    opportunity, _ = submit_pitch(
        PipelineDeps(deps.crm, deps.llm, enricher, deps.thesis), pitch_of(samples, "clean-abc-ai")
    )
    assert opportunity.processing_state == "completed"
    assert opportunity.enrichment is None
    log = next(log for log in opportunity.logs if log.step == "enriched")
    assert log.status == "failed" and "DNS lookup failed" in log.message


def test_no_website_in_pitch_skips_enrichment(deps, samples):
    enricher = FakeEnricher()
    opportunity, _ = submit_pitch(
        PipelineDeps(deps.crm, deps.llm, enricher, deps.thesis), pitch_of(samples, "no-website-startup")
    )
    assert enricher.calls == []
    assert ("enriched", "skipped") in steps(opportunity)


# ---------- retry (FR-23) ----------


def test_retry_after_llm_outage_completes_without_duplicates(deps, samples, session):
    llm = CountingLLM(deps.llm, fail_first=1)
    deps = PipelineDeps(deps.crm, llm, None, deps.thesis)

    opportunity, _ = submit_pitch(deps, pitch_of(samples, "clean-abc-ai"))
    assert opportunity.processing_state == "failed"

    retried = retry_opportunity(deps, opportunity.id)
    assert retried.processing_state == "completed"
    assert retried.error is None and retried.failed_step is None
    assert retried.verdict == "pass"
    assert count(session, Opportunity) == 1
    assert count(session, Company) == 1


def test_retry_after_crm_failure_reuses_stored_extraction(deps, samples, session):
    llm = CountingLLM(deps.llm)
    crm = FlakyCRM(deps.crm, fail_assert_times=1)
    flaky = PipelineDeps(crm, llm, None, deps.thesis)

    opportunity, _ = submit_pitch(flaky, pitch_of(samples, "clean-abc-ai"))
    assert opportunity.processing_state == "failed"
    assert opportunity.failed_step == "saved"
    assert opportunity.extracted is not None
    assert llm.calls == 1

    retried = retry_opportunity(flaky, opportunity.id)
    assert retried.processing_state == "completed"
    assert llm.calls == 1  # the LLM was not called again (no repeated side effect)
    assert count(session, Company) == 1
    assert count(session, Opportunity) == 1
    assert ("extracted", "skipped") in steps(retried)


def test_retry_of_permanently_bad_input_fails_again_without_side_effects(deps, samples, session):
    opportunity, _ = submit_pitch(deps, pitch_of(samples, "garbage"))
    retried = retry_opportunity(deps, opportunity.id)
    assert retried.processing_state == "failed"
    assert count(session, Company) == 0


def test_cannot_retry_a_completed_opportunity(deps, samples):
    opportunity, _ = submit_pitch(deps, pitch_of(samples, "clean-abc-ai"))
    with pytest.raises(NotRetryable):
        retry_opportunity(deps, opportunity.id)


def test_retry_unknown_id(deps):
    with pytest.raises(OpportunityNotFound):
        retry_opportunity(deps, 999_999)


# ---------- the full data-driven matrix ----------


def test_every_sample_behaves_as_recorded(deps, samples):
    for sample_id, sample in samples.items():
        opportunity, _ = submit_pitch(deps, PitchIn(**sample["pitch"]))
        expected = sample["expected"]
        assert opportunity.processing_state == expected["state"], sample_id
        assert opportunity.verdict == expected["verdict"], sample_id
