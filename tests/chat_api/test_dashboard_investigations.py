import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.app import app


def test_dashboard_investigations_returns_summary_and_items(monkeypatch) -> None:
    client = TestClient(app)

    def fake_list_investigations(limit: int) -> dict:
        assert limit == 50
        return {
            "summary": {
                "total_runs": 2,
                "completed": 1,
                "failed": 1,
                "running": 0,
            },
            "items": [
                {
                    "mission_id": 7,
                    "event_id": 42,
                    "status": "completed",
                    "started": "07-03 09:00",
                    "finished": "07-03 09:01",
                    "title": "Base Builder Rewards",
                    "verdict": "verified",
                    "recommended_action": "promote",
                    "similar_count": 1,
                    "has_supporting_evidence": True,
                    "error": "",
                }
            ],
        }

    monkeypatch.setattr("src.chat_api.dashboard_service.list_investigations", fake_list_investigations)

    resp = client.get("/api/v1/dashboard/investigations")

    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["total_runs"] == 2
    assert body["items"][0]["mission_id"] == 7
    assert body["items"][0]["recommended_action"] == "promote"