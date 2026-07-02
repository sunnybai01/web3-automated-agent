import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.dispatch import heartbeat as heartbeat_module


def test_heartbeat_returns_stats_without_sending_slack(monkeypatch) -> None:
    class DummySession:
        def close(self):
            pass

    sent = []

    monkeypatch.setattr(heartbeat_module, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(
        heartbeat_module,
        "get_unhealthy_sources",
        lambda db: [type("Source", (), {"source_name": "foo", "status": "down", "consecutive_failures": 3, "last_error": "404"})()],
    )
    monkeypatch.setattr(
        heartbeat_module,
        "_daily_stats",
        {"fetched": 10, "new": 0, "deduped": 9, "pushed": 0, "verified": 0, "fraud": 0},
    )

    stats = heartbeat_module.heartbeat(lambda payload: sent.append(payload))

    assert stats["fetched"] == 10
    assert stats["unhealthy"] == 1
    assert sent == []