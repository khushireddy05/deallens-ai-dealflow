from sqlalchemy import func, select

from app.models import Company, Opportunity
from app.seed import seed, seed_if_empty


def test_seed_loads_demo_data_through_the_real_pipeline(session):
    created = seed(session)
    assert created == 7

    rows = session.scalars(select(Opportunity)).all()
    by_state = {}
    for row in rows:
        by_state.setdefault((row.processing_state, row.verdict), 0)
        by_state[(row.processing_state, row.verdict)] += 1
    assert by_state == {
        ("completed", "pass"): 2,
        ("completed", "fail"): 3,
        ("completed", "maybe"): 1,
        ("failed", None): 1,
    }
    assert session.scalar(select(func.count(Company.id))) == 6
    assert {o.status for o in rows} >= {"new", "in_review", "passed", "rejected"}


def test_seed_twice_creates_no_duplicates(session):
    seed(session)
    assert seed(session) == 0
    assert session.scalar(select(func.count(Opportunity.id))) == 7


def test_seed_if_empty_does_nothing_when_data_exists(session):
    assert seed_if_empty(session) == 7
    assert seed_if_empty(session) == 0
