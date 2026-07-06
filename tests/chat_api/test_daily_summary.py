import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.app import app


def test_daily_summary_trigger_endpoint_returns_summary_result(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setitem(
        sys.modules,
        "src.main",
        SimpleNamespace(
            run_daily_summary=lambda: {
                "status": "success",
                "summary_date": "2026-07-06",
                "slack_ts": "123.456",
            }
        ),
    )

    resp = client.post("/api/v1/dashboard/daily-summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["summary_date"] == "2026-07-06"
    assert body["slack_ts"] == "123.456"


def test_daily_summary_trigger_endpoint_propagates_failure(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setitem(
        sys.modules,
        "src.main",
        SimpleNamespace(
            run_daily_summary=lambda: {
                "status": "failed",
                "summary_date": "2026-07-06",
                "error": "slack_send_failed_or_not_configured",
            }
        ),
    )

    resp = client.post("/api/v1/dashboard/daily-summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["summary_date"] == "2026-07-06"
    assert body["error"] == "slack_send_failed_or_not_configured"