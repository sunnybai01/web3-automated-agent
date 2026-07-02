import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.app import app


def test_dashboard_schedule_logs_returns_summary_and_items(monkeypatch) -> None:
    client = TestClient(app)

    def fake_list_schedule_logs(limit: int) -> dict:
        assert limit == 50
        return {
            "summary": {
                "total_runs": 4,
                "success": 3,
                "failed": 1,
                "running": 0,
            },
            "items": [
                {
                    "id": 1001,
                    "job": "fetch_all_sources",
                    "status": "success",
                    "started": "07-02 09:00",
                    "fetched": 120,
                    "new": 12,
                    "deduped": 60,
                    "classified": 40,
                    "verified": 15,
                    "error": "",
                }
            ],
        }

    monkeypatch.setattr("src.chat_api.dashboard_service.list_schedule_logs", fake_list_schedule_logs)

    resp = client.get("/api/v1/dashboard/schedule-logs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["total_runs"] == 4
    assert body["items"][0]["job"] == "fetch_all_sources"
