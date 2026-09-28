import json
import os
from pathlib import Path

# Must be set before the app modules are imported. Tests never use a real key or the demo DB.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or "sqlite:///./test_dealflow.db"
os.environ["SEED_ON_START"] = "false"
os.environ["OPENAI_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "openai"
os.environ["ENRICHMENT_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.crm.postgres import PostgresCRM  # noqa: E402
from app.db import Base, get_engine, get_sessionmaker, init_db  # noqa: E402
from app.deps import get_enricher, get_llm  # noqa: E402
from app.llm.replay import ReplayExtractor  # noqa: E402
from app.main import app  # noqa: E402
from app.pipeline import PipelineDeps  # noqa: E402
from app.screening import load_thesis  # noqa: E402

SAMPLES_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_pitches.json"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    engine = get_engine()
    from app import models  # noqa: F401

    Base.metadata.drop_all(engine)
    init_db()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with get_engine().begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture
def session():
    with get_sessionmaker()() as s:
        yield s


@pytest.fixture
def crm(session):
    return PostgresCRM(session)


@pytest.fixture
def samples() -> dict[str, dict]:
    return {s["id"]: s for s in json.loads(SAMPLES_PATH.read_text())}


@pytest.fixture
def thesis():
    return load_thesis(get_settings().thesis_path)


@pytest.fixture
def replay_llm(samples):
    return ReplayExtractor(list(samples.values()))


@pytest.fixture
def deps(crm, replay_llm, thesis):
    """Pipeline wired with the replay LLM and no enrichment."""
    return PipelineDeps(crm=crm, llm=replay_llm, enricher=None, thesis=thesis)


@pytest.fixture
def client(replay_llm):
    app.dependency_overrides[get_llm] = lambda: replay_llm
    app.dependency_overrides[get_enricher] = lambda: None
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
