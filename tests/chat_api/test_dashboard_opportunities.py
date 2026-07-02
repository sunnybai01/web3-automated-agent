import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.app import app


def test_dashboard_opportunities_returns_metrics_and_items(monkeypatch) -> None:
    client = TestClient(app)

    def fake_list_opportunities(filters):
        assert filters["days"] == 14
        assert filters["min_score"] == 5.0
        assert filters["source_trust"] == "official"
        return {
            "metrics": {
                "total_shown": 2,
                "avg_score": 7.5,
                "verified_percent": 50,
                "grants": 1,
                "bounties": 1,
                "hackathons": 0,
                "official": 1,
                "discovery": 1,
            },
            "items": [
                {
                    "id": 101,
                    "score": 8.4,
                    "type": "GRANT",
                    "title": "Sui Builder Fund",
                    "ecosystem": "sui",
                    "amount": "$10,000",
                    "deadline": "2026-07-20",
                    "heat": 3,
                    "verified": True,
                    "source_trust": "official",
                    "verification_verdict": "verified",
                    "apply_url": "https://example.com/apply",
                }
            ],
        }

    monkeypatch.setattr("src.chat_api.dashboard_service.list_opportunities", fake_list_opportunities)

    resp = client.get(
        "/api/v1/dashboard/opportunities",
        params={
            "event_types": ["grant", "hackathon", "bounty"],
            "ecosystem": "",
            "min_score": 5.0,
            "days": 14,
            "source_trust": "official",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["metrics"]["total_shown"] == 2
    assert body["metrics"]["official"] == 1
    assert body["items"][0]["id"] == 101
    assert body["items"][0]["title"] == "Sui Builder Fund"
    assert body["items"][0]["source_trust"] == "official"
    assert body["items"][0]["verification_verdict"] == "verified"