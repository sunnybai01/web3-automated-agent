import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.app import app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/chat/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
