import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from config.settings import Settings


def test_twitter_settings_have_safe_defaults(monkeypatch) -> None:
    monkeypatch.delenv("TWITTER_AUTH_INFO_1", raising=False)
    monkeypatch.delenv("TWITTER_AUTH_INFO_2", raising=False)
    monkeypatch.delenv("TWITTER_PASSWORD", raising=False)
    monkeypatch.delenv("TWITTER_TOTP_SECRET", raising=False)
    monkeypatch.delenv("TWITTER_COOKIES_FILE", raising=False)
    monkeypatch.delenv("SOCIAL_WATCH_INTERVAL_MINUTES", raising=False)
    monkeypatch.delenv("TWITTER_FETCH_COUNT", raising=False)

    settings = Settings()

    assert settings.TWITTER_AUTH_INFO_1 == ""
    assert settings.TWITTER_AUTH_INFO_2 == ""
    assert settings.TWITTER_PASSWORD == ""
    assert settings.TWITTER_TOTP_SECRET == ""
    assert settings.TWITTER_COOKIES_FILE == ".twitter-cookies.json"
    assert settings.SOCIAL_WATCH_INTERVAL_MINUTES == 15
    assert settings.TWITTER_FETCH_COUNT == 20


def test_tavily_cooldown_has_safe_default(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_SUCCESS_COOLDOWN_MINUTES", raising=False)
    monkeypatch.delenv("TAVILY_MAX_SOURCES_PER_RUN", raising=False)

    settings = Settings()

    assert settings.TAVILY_SUCCESS_COOLDOWN_MINUTES == 1440
    assert settings.TAVILY_MAX_SOURCES_PER_RUN == 1


def test_daily_summary_settings_have_safe_defaults(monkeypatch) -> None:
    monkeypatch.delenv("DAILY_SUMMARY_ENABLED", raising=False)
    monkeypatch.delenv("DAILY_SUMMARY_CRON", raising=False)

    settings = Settings()

    assert settings.DAILY_SUMMARY_ENABLED is True
    assert settings.DAILY_SUMMARY_CRON == "55 23 * * *"
