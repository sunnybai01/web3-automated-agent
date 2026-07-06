"""Web3 Intelligence Agent — Main Entry Point.

Wires together the full V1 pipeline:
  Fetcher → L1 Dedup → L2 Dedup → LLM Classify → Zero-trust Verify → Score → Slack Push
"""
import logging
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from config.settings import settings
from src.db.database import init_db, SessionLocal
from src.fetchers.builder import load_sources_config, build_registry
from src.fetchers.base import get_fetch_skip_reason, select_budgeted_sources
from src.dedup.url_dedup import process_item_l1
from src.dedup.content_dedup import ContentDeduplicator
from src.dedup.vector_store import VectorStore
from src.classifier.keyword_filter import KeywordFilter
from src.classifier.llm_gateway import LLMGateway
from src.classifier.classifier import OpportunityClassifier
from src.classifier.scorer import OpportunityScorer
from src.verifier.verifier import verify_opportunity
from src.dispatch.slack_client import SlackDispatcher
from src.dispatch.daily_summary_service import build_daily_summary
from src.dispatch.report_writer import generate_report
from src.dispatch.heartbeat import heartbeat, increment_stat, reset_daily_stats
from src.scheduler.jobs import create_scheduler, register_jobs
from scripts.sync_defillama_chains import sync_candidate_snapshot
from src.db.queries import (
    upsert_source_health,
    get_source_health,
    create_schedule_log,
    finish_schedule_log,
    update_event,
    get_push_log_for_event,
    create_push_log,
    get_daily_summary_log,
    create_daily_summary_log,
    mark_daily_summary_sent,
    mark_daily_summary_failed,
)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline components (initialized once)
# ---------------------------------------------------------------------------
_fetcher_registry = None
_deduplicator = None
_classifier = None
_scorer = None
_slack = None
_stats_reset_day = datetime.now(timezone.utc).day
STALE_EVENT_MAX_AGE = timedelta(days=7)

EVENT_MODEL_FIELDS = {
    "event_type",
    "title",
    "description",
    "deadline",
    "amount",
    "track",
    "ecosystem",
    "application_url",
    "source_url",
    "source_platform",
}


def _init_components():
    global _fetcher_registry, _deduplicator, _classifier, _scorer, _slack

    if _fetcher_registry is None:
        config = load_sources_config()
        _fetcher_registry = build_registry(config)

    if _deduplicator is None:
        vs = VectorStore()
        _deduplicator = ContentDeduplicator(vs)

    if _classifier is None:
        kw = KeywordFilter()
        llm = LLMGateway()
        _classifier = OpportunityClassifier(kw, llm)
        _scorer = OpportunityScorer(llm)

    if _slack is None:
        _slack = SlackDispatcher()


def _init_slack():
    global _slack

    if _slack is None:
        _slack = SlackDispatcher()


def _persistable_event_data(event_data: dict) -> dict:
    return {
        key: value
        for key, value in event_data.items()
        if key in EVENT_MODEL_FIELDS
    }


def _parse_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _published_at(item) -> datetime | None:
    metadata = item.metadata or {}
    for key in ("created_at", "published_at", "published_date", "published"):
        published_at = _parse_datetime(metadata.get(key))
        if published_at is not None:
            return published_at
    return None


def _staleness_reason(item, structured: dict | None, now: datetime | None = None) -> str | None:
    now = now or datetime.now(timezone.utc)

    published_at = _published_at(item)
    if published_at is not None and now - published_at > STALE_EVENT_MAX_AGE:
        return "published_too_old"

    deadline = _parse_datetime((structured or {}).get("deadline"))
    if deadline is not None and deadline < now:
        return "deadline_expired"

    return None


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------
def run_pipeline(schedule: str):
    """Run the full pipeline for one schedule type (grant_hackathon | bounty)."""
    global _stats_reset_day

    _init_components()

    # Reset daily stats if day changed
    today = datetime.now(timezone.utc).day
    if today != _stats_reset_day:
        reset_daily_stats()
        _stats_reset_day = today

    db = SessionLocal()
    log = create_schedule_log(db, f"pipeline_{schedule}")
    stats = {"fetched": 0, "new": 0, "deduped": 0, "classified": 0,
             "verified": 0, "fraud": 0, "pushed": 0}
    result = None

    try:
        fetcher_sources = [
            {**fetcher.config, "name": name}
            for name, fetcher in _fetcher_registry._fetchers.items()
        ]
        health_by_source = {
            source["name"]: get_source_health(db, source["name"])
            for source in fetcher_sources
        }
        tavily_allowed = select_budgeted_sources(
            fetcher_sources,
            health_by_source,
            schedule,
            fetch_method="tavily_search",
        )

        # --- Phase 1: Fetch ---
        def _should_skip_fetch(name, fetcher):
            if fetcher.config.get("fetch_method") == "tavily_search" and name not in tavily_allowed:
                return "method_budget"
            health = health_by_source.get(name)
            return get_fetch_skip_reason(fetcher.config, health)

        items, source_status = _fetcher_registry.fetch_all_with_status(
            schedule,
            should_skip=_should_skip_fetch,
        )
        stats["fetched"] = len(items)
        increment_stat("fetched", len(items))
        logger.info(f"[{schedule}] Fetched {len(items)} items from {len(_fetcher_registry._fetchers)} sources")

        # Update source health at source-level granularity
        for name, status in source_status.items():
            if status.get("skipped"):
                continue
            upsert_source_health(
                db,
                name,
                success=status.get("success", False),
                error=status.get("error"),
            )

        # --- Phase 2: L1 URL Dedup ---
        l1_results = []
        for item in items:
            signal_id = process_item_l1(db, item)
            if signal_id:
                l1_results.append((item, signal_id))
            else:
                stats["deduped"] += 1
        logger.info(f"[{schedule}] L1 dedup: {len(l1_results)} passed, {stats['deduped']} duplicates")

        # --- Phase 3+4+5+6+7: Classify → Dedup → Verify → Score → Collect ---
        new_events = []  # collected for report generation

        for item, signal_id in l1_results:
            category, structured = _classifier.classify(item)
            if category is None or category == "NOISE":
                continue
            stats["classified"] += 1

            staleness_reason = _staleness_reason(item, structured)
            if staleness_reason:
                logger.info("[%s] Skip stale item from %s: %s", schedule, item.source_name, staleness_reason)
                continue

            source_metadata = {
                "chain": item.metadata.get("chain"),
                "source_tier": item.metadata.get("source_tier"),
                "official": item.metadata.get("official"),
                "signal_type": item.metadata.get("signal_type"),
            }

            # --- Phase 4: L2 Semantic Dedup ---
            event_data = {
                "event_type": category.lower(),
                "title": structured.get("title", ""),
                "description": structured.get("description", ""),
                "deadline": structured.get("deadline"),
                "amount": structured.get("amount"),
                "track": structured.get("track"),
                "ecosystem": structured.get("ecosystem"),
                "application_url": structured.get("application_url"),
                "source_url": item.raw_url,
                "source_platform": structured.get("source_platform") or item.source_name,
                **source_metadata,
            }

            event_id, is_new = _deduplicator.check_and_process(
                db, _persistable_event_data(event_data),
                source_type=item.source_type,
                source_name=item.source_name,
                source_url=item.raw_url,
                raw_signal_id=signal_id,
            )

            if not is_new:
                stats["deduped"] += 1
                increment_stat("deduped")
                continue

            stats["new"] += 1
            increment_stat("new")

            # --- Phase 5: Zero-trust Verification ---
            verification = verify_opportunity(
                event_type=category.lower(),
                source_url=item.raw_url,
                application_url=structured.get("application_url", ""),
                source_name=item.source_name,
                metadata=item.metadata,
            )

            if verification["verdict"] == "fraud":
                from src.db.queries import mark_event_fraud
                mark_event_fraud(db, event_id, verification["verification_log"])
                stats["fraud"] += 1
                increment_stat("fraud")
                continue

            stats["verified"] += 1
            increment_stat("verified")
            event_data["verification_verdict"] = verification["verdict"]
            event_data["verification_log"] = verification["verification_log"]

            # --- Phase 6: Scoring ---
            scored = _scorer.score(event_data)
            if scored:
                update_event(db, event_id,
                            is_verified=True,
                            verification_log=verification["verification_log"],
                            score_roi=scored.get("score_roi"),
                            score_reputation=scored.get("score_reputation"),
                            score_timeliness=scored.get("score_timeliness"),
                            score_strategy=scored.get("score_strategy"),
                            final_score=scored.get("final_score"),
                            )

            # --- Phase 7: Push to Slack (if configured) ---
            full_event = {**event_data, "id": event_id, **scored} if scored else {**event_data, "id": event_id}
            slack_ts = _slack.push_new_event(full_event)

            if slack_ts:
                update_event(db, event_id, status="pushed", slack_ts=slack_ts,
                            slack_channel_id=settings.SLACK_CHANNEL_ID)
                create_push_log(db, event_id, action="create", slack_ts=slack_ts, success=True)
                stats["pushed"] += 1
                increment_stat("pushed")
            else:
                # Not pushed via Slack (either not configured or failed)
                # Event is still recorded for the Markdown report
                pass

            new_events.append(full_event)

        # --- Generate and send report only when effective opportunities exist ---
        if new_events:
            report_path = None
            try:
                report_path = generate_report(new_events, schedule, stats)
                logger.info(f"Report saved: {report_path}")
            except Exception as e:
                logger.error(f"Report generation failed: {e}")

            if report_path and _slack.is_configured:
                _slack.upload_report(report_path, schedule, stats)
        else:
            logger.info(f"[{schedule}] No effective events found; skip Slack cards/report upload")

        finish_schedule_log(db, log.id, items_fetched=stats["fetched"],
                           items_new=stats["new"], items_deduped=stats["deduped"],
                           items_classified=stats["classified"],
                           items_verified=stats["verified"])
        logger.info(f"[{schedule}] Complete: {stats}")
        result = {"status": "success", **stats}

    except Exception as e:
        logger.exception(f"[{schedule}] Pipeline failed: {e}")
        finish_schedule_log(db, log.id, error=str(e))
        # Update source health for failed sources
        for name in _fetcher_registry._fetchers:
            upsert_source_health(db, name, success=False, error=str(e))
        result = {"status": "failed", "error": str(e), **stats}

    finally:
        db.close()

    return result


def run_heartbeat():
    """Send heartbeat and check source health."""
    _init_components()

    def _hb_slack(stats_or_msg):
        if isinstance(stats_or_msg, str):
            _slack.send_alert(stats_or_msg)
        else:
            _slack.send_heartbeat(stats_or_msg)

    heartbeat(_hb_slack)


def run_defillama_candidate_sync():
    """Refresh the DefiLlama candidate chain snapshot on schedule."""
    snapshot = sync_candidate_snapshot()
    logger.info(
        "DefiLlama candidate sync complete: %s chains",
        len(snapshot.get("candidate_chains", [])),
    )


def run_social_watch():
    """Run the dedicated social watch schedule."""
    return run_pipeline("social_watch")


def run_daily_summary():
    """Build and send the once-per-day Slack summary."""
    _init_slack()

    db = SessionLocal()
    try:
        summary_date = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        existing = get_daily_summary_log(db, summary_date=summary_date, channel="slack")
        if existing is not None and existing.status == "success":
            logger.info("Daily summary already sent for %s; skipping", summary_date.isoformat())
            return {"status": "skipped", "summary_date": summary_date.isoformat()}

        log_row = existing or create_daily_summary_log(db, summary_date=summary_date, channel="slack")
        payload = build_daily_summary(db, summary_date=summary_date)
        payload["totals"]["pushed"] = payload["totals"].get("pushed", 0)

        slack_ts = _slack.send_daily_summary(payload)
        if not slack_ts:
            mark_daily_summary_failed(db, log_row.id, error_message="slack_send_failed_or_not_configured")
            return {
                "status": "failed",
                "summary_date": summary_date.isoformat(),
                "error": "slack_send_failed_or_not_configured",
            }

        mark_daily_summary_sent(db, log_row.id, slack_ts=slack_ts)
        logger.info("Daily summary sent for %s", summary_date.isoformat())
        return {"status": "success", "summary_date": summary_date.isoformat(), "slack_ts": slack_ts}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    logger.info("Starting Web3 Intelligence Agent V1...")

    # Initialize database tables
    init_db()
    logger.info("Database initialized")

    # Create scheduler
    scheduler = create_scheduler()
    register_jobs(scheduler, run_pipeline, run_heartbeat, run_defillama_candidate_sync, run_social_watch, run_daily_summary)
    scheduler.start()
    logger.info("Scheduler started — waiting for jobs...")

    try:
        # Keep the main thread alive
        import signal
        stop_event = __import__("threading").Event()

        def _shutdown(sig, frame):
            logger.info("Shutdown signal received")
            stop_event.set()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        # Run once immediately on startup, then wait for cron
        logger.info("Running initial pipeline pass...")
        run_pipeline("grant_hackathon")
        run_pipeline("bounty")
        run_social_watch()
        run_heartbeat()

        stop_event.wait()

    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown(wait=False)
        if _fetcher_registry:
            _fetcher_registry.close()
        logger.info("Agent shut down")


if __name__ == "__main__":
    main()
