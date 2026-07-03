import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.fetchers.base import FetchedItem
from src.main import _persistable_event_data, _staleness_reason, run_pipeline


def test_main_declares_run_social_watch_wrapper() -> None:
    source = Path("src/main.py").read_text(encoding="utf-8")
    module = ast.parse(source)

    function = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_social_watch"
    )

    assert len(function.body) == 2
    assert isinstance(function.body[1], ast.Return)

    call = function.body[1].value
    assert isinstance(call, ast.Call)
    assert isinstance(call.func, ast.Name)
    assert call.func.id == "run_pipeline"
    assert len(call.args) == 1
    assert isinstance(call.args[0], ast.Constant)
    assert call.args[0].value == "social_watch"


def test_persistable_event_data_strips_non_event_model_fields() -> None:
    event_data = {
        "event_type": "grant",
        "title": "ESP Grants",
        "description": "Support for ecosystem teams",
        "ecosystem": "ethereum",
        "application_url": "https://esp.ethereum.foundation/apply",
        "source_url": "https://x.com/EF_ESP/status/1",
        "source_platform": "twitter_ef_esp",
        "chain": "ethereum",
        "source_tier": "official",
        "official": True,
        "signal_type": "social",
    }

    persisted = _persistable_event_data(event_data)

    assert persisted["event_type"] == "grant"
    assert persisted["ecosystem"] == "ethereum"
    assert "chain" not in persisted
    assert "source_tier" not in persisted
    assert "official" not in persisted
    assert "signal_type" not in persisted


def test_staleness_reason_marks_items_older_than_seven_days() -> None:
    now = datetime(2026, 7, 3, tzinfo=timezone.utc)
    item = FetchedItem(
        source_type="twitter",
        source_name="twitter_gitcoin",
        raw_content="grant round open",
        raw_url="https://x.com/gitcoin/status/1",
        canonical_url="https://x.com/gitcoin/status/1",
        metadata={
            "created_at": (now - timedelta(days=8)).isoformat(),
        },
    )

    assert _staleness_reason(item, {"deadline": "2026-07-20T00:00:00+00:00"}, now=now) == "published_too_old"


def test_staleness_reason_marks_items_with_past_deadline() -> None:
    now = datetime(2026, 7, 3, tzinfo=timezone.utc)
    item = FetchedItem(
        source_type="twitter",
        source_name="twitter_gitcoin",
        raw_content="grant round open",
        raw_url="https://x.com/gitcoin/status/1",
        canonical_url="https://x.com/gitcoin/status/1",
        metadata={},
    )

    assert _staleness_reason(item, {"deadline": "2026-07-01T00:00:00+00:00"}, now=now) == "deadline_expired"


def test_run_pipeline_skips_stale_items_before_dedup(monkeypatch) -> None:
    fake_db = SimpleNamespace(close=lambda: None)
    finished = {}

    class FakeRegistry:
        _fetchers = {"twitter_gitcoin": object()}

        def fetch_all_with_status(self, schedule, should_skip=None):
            item = FetchedItem(
                source_type="twitter",
                source_name="twitter_gitcoin",
                raw_content="grant round open",
                raw_url="https://x.com/gitcoin/status/1",
                canonical_url="https://x.com/gitcoin/status/1",
                metadata={
                    "created_at": "2026-06-20T00:00:00+00:00",
                    "chain": "multi",
                    "source_tier": "official",
                    "official": True,
                    "signal_type": "social",
                },
            )
            return [item], {"twitter_gitcoin": {"success": True, "error": None, "skipped": None}}

    class FakeClassifier:
        def classify(self, item):
            return "GRANT", {
                "title": "Gitcoin Grants",
                "description": "Open round",
                "ecosystem": "multi",
                "application_url": "https://gitcoin.co",
                "deadline": "2026-07-20T00:00:00+00:00",
            }

    class RaisingDeduplicator:
        def check_and_process(self, *args, **kwargs):
            raise AssertionError("stale items should not reach deduplicator")

    monkeypatch.setattr("src.main.SessionLocal", lambda: fake_db)
    monkeypatch.setattr("src.main.create_schedule_log", lambda db, name: SimpleNamespace(id=999))
    monkeypatch.setattr(
        "src.main.finish_schedule_log",
        lambda db, log_id, **kwargs: finished.update({"log_id": log_id, **kwargs}),
    )
    monkeypatch.setattr("src.main.upsert_source_health", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.main.get_source_health", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.main.process_item_l1", lambda db, item: 123)
    monkeypatch.setattr("src.main.increment_stat", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.main._init_components", lambda: None)
    monkeypatch.setattr("src.main._fetcher_registry", FakeRegistry())
    monkeypatch.setattr("src.main._classifier", FakeClassifier())
    monkeypatch.setattr("src.main._deduplicator", RaisingDeduplicator())
    monkeypatch.setattr("src.main._slack", SimpleNamespace(is_configured=False))

    result = run_pipeline("social_watch")

    assert result["status"] == "success"
    assert result["fetched"] == 1
    assert result["classified"] == 1
    assert result["new"] == 0
    assert result["verified"] == 0
    assert finished["log_id"] == 999
    assert finished["items_fetched"] == 1
    assert finished["items_new"] == 0


def test_run_pipeline_failure_finishes_schedule_log_with_error(monkeypatch) -> None:
    fake_db = SimpleNamespace(close=lambda: None)
    finished = {}

    class FakeRegistry:
        _fetchers = {"twitter_gitcoin": object()}

        def fetch_all_with_status(self, schedule, should_skip=None):
            item = FetchedItem(
                source_type="twitter",
                source_name="twitter_gitcoin",
                raw_content="grant round open",
                raw_url="https://x.com/gitcoin/status/1",
                canonical_url="https://x.com/gitcoin/status/1",
                metadata={
                    "chain": "multi",
                    "source_tier": "official",
                    "official": True,
                    "signal_type": "social",
                },
            )
            return [item], {"twitter_gitcoin": {"success": True, "error": None, "skipped": None}}

    class FakeClassifier:
        def classify(self, item):
            return "GRANT", {
                "title": "Gitcoin Grants",
                "description": "Open round",
                "ecosystem": "multi",
                "application_url": "https://gitcoin.co",
            }

    class FailingDeduplicator:
        def check_and_process(self, *args, **kwargs):
            raise TypeError("'chain' is an invalid keyword argument for Event")

    monkeypatch.setattr("src.main.SessionLocal", lambda: fake_db)
    monkeypatch.setattr("src.main.create_schedule_log", lambda db, name: SimpleNamespace(id=999))
    monkeypatch.setattr(
        "src.main.finish_schedule_log",
        lambda db, log_id, **kwargs: finished.update({"log_id": log_id, **kwargs}),
    )
    monkeypatch.setattr("src.main.upsert_source_health", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.main.get_source_health", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.main.process_item_l1", lambda db, item: 123)
    monkeypatch.setattr("src.main.increment_stat", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.main._init_components", lambda: None)
    monkeypatch.setattr("src.main._fetcher_registry", FakeRegistry())
    monkeypatch.setattr("src.main._classifier", FakeClassifier())
    monkeypatch.setattr("src.main._deduplicator", FailingDeduplicator())
    monkeypatch.setattr("src.main._scorer", None)
    monkeypatch.setattr("src.main._slack", SimpleNamespace(is_configured=False))

    result = run_pipeline("social_watch")

    assert result["status"] == "failed"
    assert "invalid keyword argument" in result["error"]
    assert finished["log_id"] == 999
    assert finished["error"] == result["error"]