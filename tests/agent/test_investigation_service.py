import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.db.database import Base
from src.db.models import Event


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")

    # Import agent models once they exist and register on Base metadata.
    import src.db.models as _models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_investigate_event_records_mission_and_trajectory(db_session, monkeypatch) -> None:
    from src.agent.investigation_service import investigate_event
    from src.db.models import AgentMission, AgentTrajectory

    event = Event(
        event_type="grant",
        title="Base Builder Rewards",
        description="Funding opportunity for builders.",
        ecosystem="base",
        application_url="https://apply.base.org",
        source_url="https://base.org/grants",
        source_platform="base_blog",
        heat_count=2,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    monkeypatch.setattr(
        "src.agent.investigation_service.verify_opportunity",
        lambda **kwargs: {
            "is_verified": True,
            "verdict": "verified",
            "verification_log": {
                "layers": {
                    "origin_anchor": {"passed": True, "reason": "domain_match:base.org"},
                    "cross_reference": {"passed": True, "reason": "application_url_reachable"},
                    "security_api": {"passed": True, "reason": "all_security_checks_passed"},
                }
            },
        },
    )
    monkeypatch.setattr(
        "src.agent.investigation_service._retrieve_similar_events",
        lambda db, event, limit=3: [],
    )
    monkeypatch.setattr(
        "src.agent.investigation_service._fetch_supporting_page_evidence",
        lambda event: None,
    )

    result = investigate_event(db_session, event.id)

    assert result["status"] == "completed"
    assert result["event_id"] == event.id
    assert result["mission"]["event_id"] == event.id
    assert result["conclusion"]["verdict"] == "verified"
    assert result["conclusion"]["recommended_action"] == "promote"
    assert [step["action"] for step in result["trajectory"]] == [
        "load_event",
        "retrieve_similar_events",
        "fetch_supporting_evidence",
        "verify_event",
        "finalize_conclusion",
    ]

    mission = db_session.query(AgentMission).one()
    assert mission.event_id == event.id
    assert mission.status == "completed"
    assert mission.goal == f"investigate_event:{event.id}"

    trajectories = db_session.query(AgentTrajectory).order_by(AgentTrajectory.step_index.asc()).all()
    assert [row.action for row in trajectories] == [
        "load_event",
        "retrieve_similar_events",
        "fetch_supporting_evidence",
        "verify_event",
        "finalize_conclusion",
    ]
    assert trajectories[-1].observation["recommended_action"] == "promote"


def test_investigate_event_marks_missing_event_as_failed(db_session) -> None:
    from src.agent.investigation_service import investigate_event
    from src.db.models import AgentMission, AgentTrajectory

    result = investigate_event(db_session, 999999)

    assert result["status"] == "failed"
    assert result["error"] == "event_not_found"
    assert result["trajectory"][0]["action"] == "load_event"

    mission = db_session.query(AgentMission).one()
    assert mission.status == "failed"
    assert mission.event_id == 999999

    trajectories = db_session.query(AgentTrajectory).order_by(AgentTrajectory.step_index.asc()).all()
    assert len(trajectories) == 1
    assert trajectories[0].action == "load_event"
    assert trajectories[0].observation["error"] == "event_not_found"


def test_investigate_event_retrieves_similar_events(db_session, monkeypatch) -> None:
    from src.agent.investigation_service import investigate_event
    from src.db.models import AgentTrajectory

    event = Event(
        event_type="grant",
        title="Base Builder Rewards",
        description="Funding opportunity for builders.",
        ecosystem="base",
        application_url="https://apply.base.org",
        source_url="https://base.org/grants",
        source_platform="base_blog",
        heat_count=2,
    )
    similar_event = Event(
        event_type="grant",
        title="Base Ecosystem Grants",
        description="Historical grants program for Base builders.",
        ecosystem="base",
        application_url="https://apply.base.org/grants",
        source_url="https://base.org/grants/history",
        source_platform="base_blog",
        heat_count=3,
    )
    db_session.add_all([event, similar_event])
    db_session.commit()
    db_session.refresh(event)
    db_session.refresh(similar_event)

    class FakeVectorStore:
        def search_similar(self, text, n_results=5, where=None):
            return [
                (f"event_{event.id}", 0.0, {"ecosystem": "base"}),
                (f"event_{similar_event.id}", 0.12, {"ecosystem": "base"}),
            ]

    monkeypatch.setattr(
        "src.agent.investigation_service._build_vector_store",
        lambda: FakeVectorStore(),
    )
    monkeypatch.setattr(
        "src.agent.investigation_service.verify_opportunity",
        lambda **kwargs: {
            "is_verified": True,
            "verdict": "verified",
            "verification_log": {"layers": {}},
        },
    )
    monkeypatch.setattr(
        "src.agent.investigation_service._fetch_supporting_page_evidence",
        lambda event: None,
    )

    result = investigate_event(db_session, event.id)

    assert result["status"] == "completed"
    assert result["conclusion"]["similar_events"] == [
        {
            "event_id": similar_event.id,
            "title": "Base Ecosystem Grants",
            "ecosystem": "base",
            "similarity": 0.88,
        }
    ]
    assert result["trajectory"][1]["action"] == "retrieve_similar_events"

    trajectories = db_session.query(AgentTrajectory).order_by(AgentTrajectory.step_index.asc()).all()
    assert [row.action for row in trajectories] == [
        "load_event",
        "retrieve_similar_events",
        "fetch_supporting_evidence",
        "verify_event",
        "finalize_conclusion",
    ]
    assert trajectories[1].observation["similar_events_count"] == 1


def test_investigate_event_fetches_supporting_page_evidence(db_session, monkeypatch) -> None:
    from src.agent.investigation_service import investigate_event
    from src.db.models import AgentTrajectory

    event = Event(
        event_type="grant",
        title="Base Builder Rewards",
        description="Funding opportunity for builders.",
        ecosystem="base",
        application_url="https://apply.base.org",
        source_url="https://base.org/grants",
        source_platform="base_blog",
        heat_count=2,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    monkeypatch.setattr(
        "src.agent.investigation_service._retrieve_similar_events",
        lambda db, event, limit=3: [],
    )
    monkeypatch.setattr(
        "src.agent.investigation_service._fetch_supporting_page_evidence",
        lambda event: {
            "url": "https://apply.base.org",
            "title": "Base Builder Rewards",
            "excerpt": "Applications are open for Base builders.",
        },
    )
    monkeypatch.setattr(
        "src.agent.investigation_service.verify_opportunity",
        lambda **kwargs: {
            "is_verified": True,
            "verdict": "verified",
            "verification_log": {"layers": {}},
        },
    )

    result = investigate_event(db_session, event.id)

    assert result["status"] == "completed"
    assert result["conclusion"]["supporting_evidence"] == {
        "url": "https://apply.base.org",
        "title": "Base Builder Rewards",
        "excerpt": "Applications are open for Base builders.",
    }
    assert result["trajectory"][2]["action"] == "fetch_supporting_evidence"

    trajectories = db_session.query(AgentTrajectory).order_by(AgentTrajectory.step_index.asc()).all()
    assert trajectories[2].action == "fetch_supporting_evidence"
    assert trajectories[2].observation["title"] == "Base Builder Rewards"