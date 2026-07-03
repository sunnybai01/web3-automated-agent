import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.fetchers.twitter_fetcher import TwitterFetcher


class _FakeClient:
    def head(self, url: str, follow_redirects: bool = True):
        return httpx.Response(200, request=httpx.Request("HEAD", url), url=url)

    def close(self) -> None:
        return None


def test_twitter_fetcher_builds_fetched_items_from_account_timeline(monkeypatch) -> None:
    class FakeTwitterClient:
        def fetch_account_tweets(self, *, screen_name: str, count: int, cursor: str | None):
            assert screen_name == "base"
            assert count == 20
            assert cursor is None
            return [
                {
                    "id": "1001",
                    "url": "https://x.com/base/status/1001",
                    "text": "Base Builder Rewards is now open. Apply now: https://base.org/apply",
                    "author_screen_name": "base",
                    "quoted_text": "",
                    "link_urls": ["https://base.org/apply"],
                    "created_at": datetime(2026, 7, 3, 2, 0, tzinfo=timezone.utc),
                }
            ], "NEXT_CURSOR"

    saved_state = {}

    monkeypatch.setattr("src.fetchers.twitter_fetcher.TwikitTimelineClient", lambda settings: FakeTwitterClient())
    monkeypatch.setattr("src.fetchers.twitter_fetcher._load_twitter_state", lambda source_name: None)
    monkeypatch.setattr(
        "src.fetchers.twitter_fetcher._save_twitter_state",
        lambda source_name, **kwargs: saved_state.update({"source_name": source_name, **kwargs}),
    )

    fetcher = TwitterFetcher(
        "twitter_base",
        {
            "screen_name": "base",
            "source_kind": "account",
            "ingestion_mode": "direct",
            "trust_tier": "official",
            "fetch_method": "twitter",
            "category": "social",
            "ecosystem": "base",
        },
        http_client=_FakeClient(),
    )

    items = fetcher.fetch()

    assert len(items) == 1
    assert items[0].source_type == "twitter"
    assert items[0].metadata["tweet_id"] == "1001"
    assert items[0].metadata["created_at"] == datetime(2026, 7, 3, 2, 0, tzinfo=timezone.utc)
    assert items[0].metadata["trust_tier"] == "official"
    assert items[0].metadata["preprocess_verdict"] == "strong_candidate"
    assert items[0].canonical_url == "https://x.com/base/status/1001"
    assert saved_state == {
        "source_name": "twitter_base",
        "last_tweet_id": "1001",
        "cursor": "NEXT_CURSOR",
    }


def test_twitter_fetcher_drops_discovery_noise_when_preprocessed(monkeypatch) -> None:
    class FakeTwitterClient:
        def fetch_account_tweets(self, *, screen_name: str, count: int, cursor: str | None):
            return [
                {
                    "id": "2001",
                    "url": "https://x.com/alpha/status/2001",
                    "text": "BTC looks strong today. GM everyone.",
                    "author_screen_name": "alpha_watch",
                    "quoted_text": "",
                    "link_urls": [],
                }
            ], None

    monkeypatch.setattr("src.fetchers.twitter_fetcher.TwikitTimelineClient", lambda settings: FakeTwitterClient())
    monkeypatch.setattr("src.fetchers.twitter_fetcher._load_twitter_state", lambda source_name: None)
    monkeypatch.setattr("src.fetchers.twitter_fetcher._save_twitter_state", lambda source_name, **kwargs: None)

    fetcher = TwitterFetcher(
        "twitter_alpha",
        {
            "screen_name": "alpha_watch",
            "source_kind": "account",
            "ingestion_mode": "preprocessed",
            "trust_tier": "discovery",
            "fetch_method": "twitter",
            "category": "social",
            "ecosystem": "multi",
        },
        http_client=_FakeClient(),
    )

    items = fetcher.fetch()

    assert items == []