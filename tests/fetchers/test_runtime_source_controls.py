import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.fetchers.base import BaseFetcher, get_fetch_skip_reason, select_budgeted_sources
from src.fetchers.builder import build_registry


class DummyFetcher(BaseFetcher):
    def fetch(self):
        return []


def test_build_registry_skips_disabled_sources_before_fetcher_resolution(monkeypatch) -> None:
    config = {
        "sources": [
            {
                "name": "disabled_discord",
                "fetch_method": "discord_bot",
                "enabled": False,
            },
            {
                "name": "enabled_rss",
                "fetch_method": "rss",
                "enabled": True,
            },
        ]
    }

    def fake_resolve(fetch_method: str):
        if fetch_method == "discord_bot":
            raise AssertionError("disabled source should not be resolved")
        return DummyFetcher

    monkeypatch.setattr("src.fetchers.builder._resolve_fetcher_class", fake_resolve)

    registry = build_registry(config)

    assert registry.all_names() == ["enabled_rss"]
    registry.close()


def test_get_fetch_skip_reason_respects_rate_limit_cooldown() -> None:
    now = dt.datetime(2026, 7, 2, 8, 0, tzinfo=dt.timezone.utc)
    health = SimpleNamespace(
        status="degraded",
        last_error="Client error '429 Too Many Requests' for url 'https://aptosfoundation.org/rss'",
        last_fetch_at=now - dt.timedelta(minutes=30),
    )

    reason = get_fetch_skip_reason(
        {
            "name": "aptos_foundation",
            "rate_limit_cooldown_minutes": 120,
        },
        health,
        now=now,
    )

    assert reason == "rate_limited_cooldown"


def test_get_fetch_skip_reason_respects_twitter_state_cooldown() -> None:
    now = dt.datetime(2026, 7, 3, 8, 0, tzinfo=dt.timezone.utc)
    state = SimpleNamespace(cooldown_until=now + dt.timedelta(minutes=10))

    reason = get_fetch_skip_reason(
        {
            "name": "twitter_base",
            "fetch_method": "twitter",
        },
        None,
        now=now,
        source_state=state,
    )

    assert reason == "source_state_cooldown"


def test_get_fetch_skip_reason_respects_success_cooldown() -> None:
    now = dt.datetime(2026, 7, 3, 8, 0, tzinfo=dt.timezone.utc)
    health = SimpleNamespace(
        status="healthy",
        last_error=None,
        last_fetch_at=now - dt.timedelta(minutes=20),
        last_success_at=now - dt.timedelta(minutes=20),
    )

    reason = get_fetch_skip_reason(
        {
            "name": "defillama_base_bounty",
            "fetch_method": "tavily_search",
            "success_cooldown_minutes": 2880,
        },
        health,
        now=now,
    )

    assert reason == "success_cooldown"


def test_select_budgeted_sources_prefers_oldest_fetches() -> None:
    sources = [
        {"name": "t1", "fetch_method": "tavily_search", "enabled": True, "schedule": "bounty", "max_sources_per_run": 2},
        {"name": "t2", "fetch_method": "tavily_search", "enabled": True, "schedule": "bounty", "max_sources_per_run": 2},
        {"name": "t3", "fetch_method": "tavily_search", "enabled": True, "schedule": "bounty", "max_sources_per_run": 2},
        {"name": "rss1", "fetch_method": "rss", "enabled": True, "schedule": "bounty"},
    ]
    now = dt.datetime(2026, 7, 3, 12, 0, tzinfo=dt.timezone.utc)
    health_by_source = {
        "t1": SimpleNamespace(last_fetch_at=now - dt.timedelta(days=1)),
        "t2": SimpleNamespace(last_fetch_at=now - dt.timedelta(days=3)),
        "t3": None,
    }

    selected = select_budgeted_sources(sources, health_by_source, "bounty", fetch_method="tavily_search")

    assert selected == {"t2", "t3"}