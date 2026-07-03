import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.classifier.keyword_filter import KeywordFilter


def test_repo_keywords_include_requested_twitter_watch_terms() -> None:
    keywords_path = Path(__file__).resolve().parents[2] / "config" / "keywords.yaml"
    keywords = KeywordFilter(str(keywords_path)).keywords

    assert "grant program" in keywords["grant"]
    assert "RFPs" in keywords["grant"]
    assert "bounties" in keywords["bounty"]
    assert "bounty pool" in keywords["bounty"]
    assert "task" in keywords["bounty"]
    assert "builder" in keywords["hackathon"]
    assert "builders" in keywords["hackathon"]
    assert "cohorts" in keywords["hackathon"]
    assert "devcon" in keywords["hackathon"]
    assert "join now" in keywords["general"]
    assert "open for applications" in keywords["general"]
    assert "submit your project" in keywords["general"]


def test_keyword_filter_matches_requested_twitter_watch_copy() -> None:
    keywords_path = Path(__file__).resolve().parents[2] / "config" / "keywords.yaml"
    keyword_filter = KeywordFilter(str(keywords_path))

    text = "Builder cohorts open for applications with a new bounty pool for ecosystem grants."

    assert keyword_filter.matches(text) is True