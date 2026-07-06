import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.dispatch.slack_client import SlackDispatcher


def test_send_daily_summary_posts_message(monkeypatch) -> None:
    sent = {}

    class FakeClient:
        def chat_postMessage(self, **kwargs):
            sent.update(kwargs)
            return {"ts": "123.456"}

    dispatcher = SlackDispatcher.__new__(SlackDispatcher)
    dispatcher._configured = True
    dispatcher.client = FakeClient()
    dispatcher.channel_id = "C123"

    ts = dispatcher.send_daily_summary(
        {
            "summary_date": "2026-07-06",
            "totals": {"fetched": 60, "new": 2, "deduped": 35, "classified": 13, "verified": 4, "pushed": 1},
            "new_events_count": 1,
            "new_event_sources": ["twitter_buildonbase"],
            "new_events": [
                {"event_type": "grant", "title": "Base Builder Rewards", "final_score": 7.8}
            ],
        }
    )

    assert ts == "123.456"
    assert sent["channel"] == "C123"
    assert "Daily Summary" in sent["text"]
    assert "twitter_buildonbase" in sent["text"]