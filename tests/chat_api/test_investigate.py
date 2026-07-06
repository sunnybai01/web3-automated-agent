import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.app import app


def test_investigate_endpoint_returns_agent_conclusion(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        "src.chat_api.investigation_api_service.investigate_event_by_id",
        lambda event_id: {
            "status": "completed",
            "event_id": event_id,
            "mission": {
                "id": 7,
                "goal": f"investigate_event:{event_id}",
                "event_id": event_id,
                "status": "completed",
                "mission_type": "single_event_investigation",
                "max_steps": 5,
            },
            "conclusion": {
                "event_id": event_id,
                "title": "Base Builder Rewards",
                "verdict": "verified",
                "recommended_action": "promote",
                "summary": "Verification verdict for event 42: verified.",
                "similar_events": [],
                "supporting_evidence": {
                    "url": "https://apply.base.org",
                    "title": "Base Builder Rewards",
                    "excerpt": "Applications are open for Base builders.",
                },
            },
            "trajectory": [
                {
                    "step_index": 0,
                    "action": "load_event",
                    "thought": "Load the requested event before choosing tools.",
                    "action_input": {"event_id": event_id},
                    "observation": {"title": "Base Builder Rewards"},
                }
            ],
            "error": "",
        },
    )

    resp = client.post("/api/v1/chat/investigate", json={"event_id": 42})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["event_id"] == 42
    assert body["mission"]["id"] == 7
    assert body["conclusion"]["recommended_action"] == "promote"
    assert body["conclusion"]["supporting_evidence"]["title"] == "Base Builder Rewards"
    assert body["trajectory"][0]["action"] == "load_event"


def test_investigate_endpoint_propagates_failure(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        "src.chat_api.investigation_api_service.investigate_event_by_id",
        lambda event_id: {
            "status": "failed",
            "event_id": event_id,
            "mission": {
                "id": 9,
                "goal": f"investigate_event:{event_id}",
                "event_id": event_id,
                "status": "failed",
                "mission_type": "single_event_investigation",
                "max_steps": 5,
            },
            "conclusion": None,
            "trajectory": [
                {
                    "step_index": 0,
                    "action": "load_event",
                    "thought": "Load the requested event before choosing tools.",
                    "action_input": {"event_id": event_id},
                    "observation": {"error": "event_not_found"},
                }
            ],
            "error": "event_not_found",
        },
    )

    resp = client.post("/api/v1/chat/investigate", json={"event_id": 999999})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["error"] == "event_not_found"
    assert body["mission"]["status"] == "failed"
    assert body["trajectory"][0]["observation"]["error"] == "event_not_found"