import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Company
from app.schemas import CompanyData, PitchIn


def data(name="ABC AI", **kwargs) -> CompanyData:
    return CompanyData(name=name, **kwargs)


def test_creates_company_with_normalized_domain(crm):
    company, created = crm.assert_company(data(domain="https://www.ABC-AI.example/about", location="Berlin"))
    assert created is True
    assert company.domain == "abc-ai.example"
    assert company.needs_review is False
    assert company.location == "Berlin"


def test_same_domain_updates_instead_of_duplicating(crm, session):
    first, _ = crm.assert_company(data(domain="abc.ai", location="Berlin"))
    second, created = crm.assert_company(data(name="ABC AI GmbH", domain="www.abc.ai", industry="AI"))
    assert created is False
    assert second.id == first.id
    assert second.industry == "AI"
    assert session.query(Company).count() == 1


def test_update_never_overwrites_a_value_with_nothing(crm):
    crm.assert_company(data(domain="abc.ai", location="Berlin", description="Original"))
    company, _ = crm.assert_company(data(domain="abc.ai", location=None, description=""))
    assert company.location == "Berlin"
    assert company.description == "Original"


def test_update_replaces_with_newer_non_empty_value(crm):
    crm.assert_company(data(domain="abc.ai", funding_stage="pre-seed"))
    company, _ = crm.assert_company(data(domain="abc.ai", funding_stage="seed"))
    assert company.funding_stage == "seed"


def test_no_domain_creates_company_flagged_for_review(crm):
    company, created = crm.assert_company(data(name="Stealth Co"))
    assert created is True
    assert company.domain is None
    assert company.needs_review is True


def test_no_domain_matches_existing_name_and_flags_review(crm, session):
    first, _ = crm.assert_company(data(name="Nova Labs", domain="nova.example"))
    second, created = crm.assert_company(data(name="NOVA LABS Inc."))
    assert created is False
    assert second.id == first.id
    assert second.needs_review is True
    assert session.query(Company).count() == 1


def test_domain_pitch_adopts_earlier_domainless_company(crm, session):
    first, _ = crm.assert_company(data(name="ABC Robotics"))
    assert first.domain is None
    second, created = crm.assert_company(data(name="ABC Robotics", domain="abc-robotics.example"))
    assert created is False
    assert second.id == first.id
    assert second.domain == "abc-robotics.example"
    assert second.needs_review is False
    assert session.query(Company).count() == 1


def test_different_companies_are_kept_apart(crm, session):
    crm.assert_company(data(name="Alpha", domain="alpha.example"))
    crm.assert_company(data(name="Beta", domain="beta.example"))
    crm.assert_company(data(name="Gamma"))
    crm.assert_company(data(name="Delta"))
    assert session.query(Company).count() == 4


def test_database_enforces_unique_domain(crm, session):
    crm.assert_company(data(domain="abc.ai"))
    session.add(Company(name="Dup", normalized_name="dup", domain="abc.ai"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_losing_a_create_race_falls_back_to_the_winner(crm, session, monkeypatch):
    """Another request inserts the same domain between our lookup and our insert."""
    winner = Company(name="Winner", normalized_name="winner", domain="race.example")
    real_find = crm.find_company_by_domain
    calls = {"n": 0}

    def find_then_appear(domain):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # our first lookup sees nothing...
        return real_find(domain)

    session.add(winner)
    session.commit()  # ...but the row is already there when we insert
    monkeypatch.setattr(crm, "find_company_by_domain", find_then_appear)

    company, created = crm.assert_company(data(name="Loser", domain="race.example", location="Rome"))
    assert created is False
    assert company.id == winner.id
    assert company.location == "Rome"
    assert session.query(Company).count() == 1


def test_create_opportunity_is_idempotent_by_key(crm):
    pitch = PitchIn(body="hello")
    first, created_first = crm.create_opportunity(pitch, "k1")
    second, created_second = crm.create_opportunity(pitch, "k1")
    assert created_first is True and created_second is False
    assert first.id == second.id


def test_list_opportunities_filters(crm):
    a, _ = crm.create_opportunity(PitchIn(body="a", subject="Alpha deal"), "ka")
    b, _ = crm.create_opportunity(PitchIn(body="b", subject="Beta deal"), "kb")
    a.verdict = "pass"
    crm.session.commit()
    crm.set_status(b, "rejected")

    assert [o.id for o in crm.list_opportunities(verdict="pass")] == [a.id]
    assert [o.id for o in crm.list_opportunities(status="rejected")] == [b.id]
    assert [o.id for o in crm.list_opportunities(q="alpha")] == [a.id]
    assert len(crm.list_opportunities()) == 2


def test_search_treats_percent_as_literal(crm):
    crm.create_opportunity(PitchIn(body="a", subject="100% growth"), "ka")
    crm.create_opportunity(PitchIn(body="b", subject="plain"), "kb")
    assert len(crm.list_opportunities(q="%")) == 1
