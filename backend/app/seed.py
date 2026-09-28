"""Load demo opportunities by running the bundled sample pitches through the real pipeline.

Uses the replay extractor (recorded LLM output), so it needs no API key and no network.
Only samples marked `"seed": true` are loaded; the rest stay available in the UI's
"Load sample" menu for trying things by hand.
"""

import json
import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .crm.postgres import PostgresCRM
from .db import get_sessionmaker, init_db
from .llm.replay import ReplayExtractor
from .models import Opportunity, utcnow
from .pipeline import PipelineDeps, submit_pitch
from .schemas import PitchIn
from .screening import load_thesis

logger = logging.getLogger(__name__)


def seed(session: Session) -> int:
    settings = get_settings()
    samples = json.loads(settings.samples_path.read_text(encoding="utf-8"))
    crm = PostgresCRM(session)
    deps = PipelineDeps(
        crm=crm,
        llm=ReplayExtractor(samples),
        enricher=None,  # never hit the network while seeding
        thesis=load_thesis(settings.thesis_path),
    )
    created_count = 0
    for sample in samples:
        if not sample.get("seed"):
            continue
        pitch = PitchIn(
            **sample["pitch"],
            received_at=utcnow() - timedelta(days=sample.get("days_ago", 0)),
        )
        opportunity, created = submit_pitch(deps, pitch)
        if created:
            created_count += 1
            if sample.get("seed_status"):
                crm.set_status(opportunity, sample["seed_status"])
    return created_count


def seed_if_empty(session: Session) -> int:
    if session.scalar(select(func.count(Opportunity.id))):
        return 0
    count = seed(session)
    logger.info("Seeded %d demo opportunities", count)
    return count


if __name__ == "__main__":
    init_db()
    with get_sessionmaker()() as db_session:
        print(f"Seeded {seed(db_session)} opportunities")
