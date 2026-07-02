import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.app import app


def test_manual_scan_status_endpoint_returns_service_snapshot(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        "src.chat_api.manual_scan_service.get_manual_scan_status",
        lambda: {
            "job_id": "job-1",
            "status": "running",
            "triggered": False,
            "started_at": "2026-07-02T00:00:00+00:00",
            "finished_at": "",
            "current_stage": "grant_hackathon",
            "schedules": [],
            "error": "",
        },
    )

    resp = client.get("/api/v1/dashboard/manual-scan")

    assert resp.status_code == 200
    assert resp.json()["status"] == "running"
    assert resp.json()["current_stage"] == "grant_hackathon"


def test_manual_scan_trigger_endpoint_starts_scan(monkeypatch) -> None:
    client = TestClient(app)

    def fake_trigger(_pipeline_runner):
        return {
            "job_id": "job-2",
            "status": "running",
            "triggered": True,
            "started_at": "2026-07-02T00:00:00+00:00",
            "finished_at": "",
            "current_stage": "grant_hackathon",
            "schedules": [],
            "error": "",
        }

    monkeypatch.setattr(
        "src.chat_api.manual_scan_service.trigger_manual_scan",
        fake_trigger,
    )
    monkeypatch.setitem(
        sys.modules,
        "src.main",
        SimpleNamespace(run_pipeline=lambda schedule: {"status": "success"}),
    )

    resp = client.post("/api/v1/dashboard/manual-scan")

    assert resp.status_code == 200
    body = resp.json()
    assert body["triggered"] is True
    assert body["status"] == "running"