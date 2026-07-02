import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.app import app


def test_verify_endpoint_returns_structured_payload(monkeypatch) -> None:
    client = TestClient(app)

    def fake_verify(target_ids):
        assert target_ids == [101]
        return {
            "score": 78,
            "level": "medium",
            "verdict": "caution",
            "evidence": [
                {
                    "category": "origin",
                    "detail": "domain match",
                    "source": "verifier_layer",
                    "weight": 20,
                    "impact": "positive",
                }
            ],
            "unknowns": [],
            "conflicts": [],
        }

    monkeypatch.setattr("src.chat_api.verify_service.verify_targets", fake_verify)

    resp = client.post("/api/v1/chat/verify", json={"target_event_ids": [101]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"] == 78
    assert "evidence" in body