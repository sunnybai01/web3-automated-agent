import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.app import app


def test_propose_options_returns_three_tiers(monkeypatch) -> None:
    client = TestClient(app)

    def fake_propose(verified_facts):
        return {
            "options": [
                {"tier": "light", "summary": "quick prototype", "assumptions": []},
                {"tier": "standard", "summary": "balanced scope", "assumptions": []},
                {"tier": "advanced", "summary": "full system", "assumptions": []},
            ]
        }

    monkeypatch.setattr("src.chat_api.proposal_service.propose_options", fake_propose)

    resp = client.post(
        "/api/v1/chat/propose-options",
        json={
            "verified_facts": {
                "title": "X Hackathon",
                "amount": "$20,000",
                "deadline": "2026-08-01",
            }
        },
    )
    assert resp.status_code == 200
    assert len(resp.json()["options"]) == 3