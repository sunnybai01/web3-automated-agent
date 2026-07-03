import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.fetchers.twitter_social import build_tweet_raw_content, preprocess_tweet


def test_social_preprocessor_drops_market_noise() -> None:
    row = {
        "id": "2001",
        "text": "BTC looks strong today. GM everyone.",
        "quoted_text": "",
        "link_urls": [],
        "author_screen_name": "macro_kol",
    }

    result = preprocess_tweet(row, trust_tier="discovery")

    assert result["verdict"] == "drop"


def test_social_preprocessor_promotes_actionable_opportunity_signal() -> None:
    row = {
        "id": "2002",
        "text": "New Solana builder grant now open. Apply before Aug 1: https://solana.org/grants",
        "quoted_text": "",
        "link_urls": ["https://solana.org/grants"],
        "author_screen_name": "alpha_researcher",
    }

    result = preprocess_tweet(row, trust_tier="discovery")

    assert result["verdict"] == "strong_candidate"
    assert result["has_official_link"] is True


def test_twitter_signal_adapter_builds_classifier_ready_content() -> None:
    row = {
        "id": "2003",
        "text": "Apply for the hackathon here",
        "quoted_text": "Prize pool is $50k",
        "link_urls": ["https://ethglobal.com/events/test"],
        "author_screen_name": "eth_watch",
        "source_kind": "list",
    }

    raw_content = build_tweet_raw_content(row)

    assert "Author: eth_watch" in raw_content
    assert "Quoted tweet: Prize pool is $50k" in raw_content
    assert "Links: https://ethglobal.com/events/test" in raw_content
    assert "Source kind: list" in raw_content