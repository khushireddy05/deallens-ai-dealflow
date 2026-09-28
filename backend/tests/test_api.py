import pytest


def pitch(samples, sample_id) -> dict:
    return samples[sample_id]["pitch"]


def submit(client, samples, sample_id):
    return client.post("/opportunities", json=pitch(samples, sample_id))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_submit_creates_then_resubmit_is_a_noop(client, samples):
    first = submit(client, samples, "clean-abc-ai")
    assert first.status_code == 201
    body = first.json()
    assert body["created"] is True
    opp = body["opportunity"]
    assert opp["processing_state"] == "completed"
    assert opp["verdict"] == "pass"
    assert opp["company"]["domain"] == "abc-ai.example"
    assert [log["step"] for log in opp["logs"]][0] == "received"

    second = submit(client, samples, "clean-abc-ai")
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["opportunity"]["id"] == opp["id"]
    assert len(client.get("/opportunities").json()) == 1
    assert len(client.get("/companies").json()) == 1


def test_second_pitch_from_same_company_shows_two_opportunities(client, samples):
    submit(client, samples, "clean-abc-ai")
    submit(client, samples, "abc-ai-followup")
    companies = client.get("/companies").json()
    assert len(companies) == 1
    assert companies[0]["opportunity_count"] == 2
    assert len(client.get("/opportunities").json()) == 2


def test_list_falls_back_to_the_company_record_for_location(client, samples):
    submit(client, samples, "clean-abc-ai")
    submit(client, samples, "abc-ai-followup")  # this pitch itself has no location
    rows = client.get("/opportunities").json()
    assert [r["location"] for r in rows] == ["Berlin", "Berlin"]
    assert [r["funding_stage"] for r in rows] == ["seed", "seed"]


@pytest.mark.parametrize("body", ["", "   \n\t "])
def test_blank_body_is_rejected(client, body):
    response = client.post("/opportunities", json={"body": body})
    assert response.status_code == 422


def test_missing_body_and_oversized_body_are_rejected(client):
    assert client.post("/opportunities", json={}).status_code == 422
    assert client.post("/opportunities", json={"body": "x" * 20001}).status_code == 422


def test_gibberish_lands_in_failures_and_nothing_reaches_the_crm(client, samples):
    response = submit(client, samples, "garbage")
    assert response.status_code == 201  # accepted and stored; processing failed
    assert response.json()["opportunity"]["processing_state"] == "failed"

    failures = client.get("/failures").json()
    assert len(failures) == 1
    assert failures[0]["failed_step"] == "extracted"
    assert client.get("/companies").json() == []


def test_retry_flow(client, samples):
    from app.deps import get_llm
    from app.main import app
    from tests.fakes import CountingLLM

    flaky = CountingLLM(app.dependency_overrides[get_llm](), fail_first=1)
    app.dependency_overrides[get_llm] = lambda: flaky

    created = submit(client, samples, "clean-abc-ai").json()["opportunity"]
    assert created["processing_state"] == "failed"

    retried = client.post(f"/opportunities/{created['id']}/retry")
    assert retried.status_code == 200
    assert retried.json()["processing_state"] == "completed"
    assert client.get("/failures").json() == []
    assert len(client.get("/companies").json()) == 1

    again = client.post(f"/opportunities/{created['id']}/retry")
    assert again.status_code == 409


def test_retry_unknown_id_is_404(client):
    assert client.post("/opportunities/9999/retry").status_code == 404


def test_status_change_persists_and_leaves_verdict_alone(client, samples):
    opp_id = submit(client, samples, "clean-abc-ai").json()["opportunity"]["id"]

    patched = client.patch(f"/opportunities/{opp_id}", json={"status": "in_review"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "in_review"

    fetched = client.get(f"/opportunities/{opp_id}").json()
    assert fetched["status"] == "in_review"
    assert fetched["verdict"] == "pass"

    client.patch(f"/opportunities/{opp_id}", json={"status": "rejected"})
    fetched = client.get(f"/opportunities/{opp_id}").json()
    assert fetched["status"] == "rejected"
    assert fetched["verdict"] == "pass"  # a human rejection does not rewrite the automated verdict


def test_invalid_status_is_rejected(client, samples):
    opp_id = submit(client, samples, "clean-abc-ai").json()["opportunity"]["id"]
    assert client.patch(f"/opportunities/{opp_id}", json={"status": "bogus"}).status_code == 422
    assert client.patch("/opportunities/9999", json={"status": "new"}).status_code == 404


def test_get_unknown_opportunity_is_404(client):
    assert client.get("/opportunities/9999").status_code == 404


def test_list_filters(client, samples):
    for sample_id in ("clean-abc-ai", "non-ai-europe", "ambiguous-stage", "garbage"):
        submit(client, samples, sample_id)

    assert len(client.get("/opportunities").json()) == 4
    passed = client.get("/opportunities", params={"verdict": "pass"}).json()
    assert [o["company_name"] for o in passed] == ["ABC AI"]
    assert len(client.get("/opportunities", params={"verdict": "fail"}).json()) == 1
    assert len(client.get("/opportunities", params={"verdict": "maybe"}).json()) == 1
    assert len(client.get("/opportunities", params={"processing_state": "failed"}).json()) == 1
    assert [o["company_name"] for o in client.get("/opportunities", params={"q": "bake"}).json()] == ["Bakehaus"]
    assert client.get("/opportunities", params={"verdict": "nonsense"}).status_code == 422


def test_list_pagination(client, samples):
    for sample_id in ("clean-abc-ai", "non-ai-europe", "ambiguous-stage"):
        submit(client, samples, sample_id)
    page = client.get("/opportunities", params={"limit": 2}).json()
    rest = client.get("/opportunities", params={"limit": 2, "offset": 2}).json()
    assert len(page) == 2 and len(rest) == 1
    assert {o["id"] for o in page}.isdisjoint({o["id"] for o in rest})


def test_companies_search_and_domain_filter(client, samples):
    submit(client, samples, "clean-abc-ai")
    submit(client, samples, "non-ai-europe")
    assert [c["name"] for c in client.get("/companies", params={"q": "bake"}).json()] == ["Bakehaus"]
    by_domain = client.get("/companies", params={"domain": "https://www.abc-ai.example/x"}).json()
    assert [c["name"] for c in by_domain] == ["ABC AI"]


def test_assert_company_endpoint_upserts(client):
    body = {"name": "Direct Co", "domain": "direct.example", "location": "Rome"}
    first = client.put("/companies/assert", json=body).json()
    assert first["created"] is True
    second = client.put("/companies/assert", json={**body, "industry": "AI"}).json()
    assert second["created"] is False
    assert second["company"]["id"] == first["company"]["id"]
    assert second["company"]["industry"] == "AI"
    assert len(client.get("/companies").json()) == 1


def test_assert_company_requires_a_name(client):
    assert client.put("/companies/assert", json={"name": ""}).status_code == 422


def test_samples_and_thesis_endpoints(client):
    samples = client.get("/samples").json()
    assert len(samples) >= 10
    assert {"id", "label", "pitch"} <= set(samples[0])
    assert "extraction" not in samples[0] and "expected" not in samples[0]

    thesis = client.get("/thesis").json()
    assert thesis["stages"] == ["pre-seed", "seed", "series-a"]
    assert "germany" in thesis["countries"]


def test_without_an_api_key_items_fail_with_a_clear_message():
    """The real dependency chain, no overrides: provider=openai and no key."""
    from fastapi.testclient import TestClient

    from app.main import app

    response = TestClient(app).post("/opportunities", json={"body": "We are Foo, an AI startup in Berlin."})
    assert response.status_code == 201
    opp = response.json()["opportunity"]
    assert opp["processing_state"] == "failed"
    assert "OPENAI_API_KEY" in opp["error"]
