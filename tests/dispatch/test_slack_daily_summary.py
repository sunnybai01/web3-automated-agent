import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.dispatch.slack_client import SlackDispatcher


def test_push_new_event_includes_source_type_label() -> None:
    sent = {}

    class FakeClient:
        def chat_postMessage(self, **kwargs):
            sent.update(kwargs)
            return {"ts": "123.456"}

    dispatcher = SlackDispatcher.__new__(SlackDispatcher)
    dispatcher._configured = True
    dispatcher.client = FakeClient()
    dispatcher.channel_id = "C123"

    ts = dispatcher.push_new_event(
        {
            "id": 42,
            "event_type": "grant",
            "title": "Base Builder Rewards",
            "description": "Funding opportunity.",
            "amount": "$50,000",
            "deadline": "2026-07-30",
            "ecosystem": "base",
            "track": "DeFi",
            "final_score": 7.8,
            "heat_count": 1,
            "verification_verdict": "verified",
            "source_url": "https://x.com/buildonbase/status/1",
            "source_type": "twitter",
        }
    )

    assert ts == "123.456"
    detail_block = sent["blocks"][1]["fields"][0]["text"]
    assert "*Source type:* Twitter" in detail_block


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
            "today_scan_stats": {
                "total_new_events": 2,
                "by_event_type": {"grant": 1, "bounty": 1},
                "by_source_type": {"twitter": 1, "rss": 1},
            },
            "historical_high_score": {
                "threshold": 7.0,
                "total_count": 3,
                "by_event_type": {"grant": 2, "bounty": 1},
                "recent_events": [
                    {
                        "event_type": "grant",
                        "title": "Base Builder Rewards",
                        "final_score": 7.8,
                        "source_type": "twitter",
                        "source_name": "twitter_buildonbase",
                        "source_url": "https://x.com/buildonbase/status/1",
                    },
                    {
                        "event_type": "bounty",
                        "title": "Arbitrum Security Bounty",
                        "final_score": 8.6,
                        "source_type": "rss",
                        "source_name": "immunefi_rss",
                        "source_url": "https://immunefi.com/bounty/arb",
                    },
                ],
            },
            "new_events_count": 1,
            "new_event_sources": ["twitter_buildonbase"],
            "new_events": [
                {
                    "event_type": "grant",
                    "title": "Base Builder Rewards",
                    "final_score": 7.8,
                    "source_type": "twitter",
                    "source_name": "twitter_buildonbase",
                    "source_url": "https://x.com/buildonbase/status/1",
                }
            ],
        }
    )

    assert ts == "123.456"
    assert sent["channel"] == "C123"
    assert "Daily Summary" in sent["text"]
    assert "twitter_buildonbase" in sent["text"]
    assert "<https://x.com/buildonbase/status/1|Base Builder Rewards>" in sent["text"]
    assert "| Source: Twitter" in sent["text"]
    assert "Today's new content stats" in sent["text"]
    assert "By event type: grant: 1, bounty: 1" in sent["text"]
    assert "Historical opportunities: 3" in sent["text"]
    assert "- [BOUNTY] <https://immunefi.com/bounty/arb|Arbitrum Security Bounty> | Score: 8.6 | Source: Rss" in sent["text"]
    assert "<https://x.com/buildonbase/status/1|twitter_buildonbase>" not in sent["text"]