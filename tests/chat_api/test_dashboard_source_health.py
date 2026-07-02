import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.app import app


def test_dashboard_source_health_returns_summary_and_items(monkeypatch) -> None:
    client = TestClient(app)

    def fake_list_source_health() -> dict:
        return {
            "summary": {
                "total_sources": 3,
                "healthy": 2,
                "degraded": 1,
                "down": 0,
            },
            "items": [
                {
                    "source": "github",
                    "status": "healthy",
                    "last_success": "2026-07-02 09:30",
                    "last_fetch": "2026-07-02 09:35",
                    "failures": 0,
                    "last_error": "",
                }
            ],
        }

    monkeypatch.setattr("src.chat_api.dashboard_service.list_source_health", fake_list_source_health)

    resp = client.get("/api/v1/dashboard/source-health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["total_sources"] == 3
    assert body["items"][0]["source"] == "github"
