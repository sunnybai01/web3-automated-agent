import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.app import app


def test_select_targets_prefers_event_id(monkeypatch) -> None:
    client = TestClient(app)

    def fake_select(params):
        assert params["event_id"] == 7
        return [7]

    monkeypatch.setattr("src.chat_api.selection_service.select_target_event_ids", fake_select)

    resp = client.post(
        "/api/v1/chat/select-targets",
        json={
            "mode": "mixed",
            "event_id": 7,
            "source_name": "rss_grants",
            "from": datetime(2026, 6, 28, tzinfo=timezone.utc).isoformat(),
            "to": datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat(),
            "limit": 20,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["target_event_ids"] == [7]
