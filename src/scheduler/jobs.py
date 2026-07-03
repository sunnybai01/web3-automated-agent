"""APScheduler job definitions — split frequency for Grant/Hackathon vs Bounty."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import settings

logger = logging.getLogger(__name__)

# Schedule definitions
GRANT_HACKATHON_SCHEDULE = "0 9,21 * * *"   # 09:00, 21:00 daily
BOUNTY_SCHEDULE = "0 */2 * * *"              # every 2 hours
HEARTBEAT_SCHEDULE = f"*/{settings.HEARTBEAT_INTERVAL_MINUTES} * * * *"
DEFILLAMA_SYNC_SCHEDULE = settings.DEFILLAMA_SYNC_CRON
SOCIAL_WATCH_INTERVAL_MINUTES = max(1, int(settings.SOCIAL_WATCH_INTERVAL_MINUTES))


def _heartbeat_trigger():
    """Build a heartbeat trigger that works for any minute interval."""
    minutes = max(1, int(settings.HEARTBEAT_INTERVAL_MINUTES))
    return IntervalTrigger(minutes=minutes)


def _social_watch_trigger():
    """Build the polling trigger for Twitter social watch."""
    return IntervalTrigger(minutes=max(1, int(settings.SOCIAL_WATCH_INTERVAL_MINUTES)))


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    return scheduler


def register_jobs(scheduler: BackgroundScheduler, pipeline_fn, heartbeat_fn, defillama_sync_fn, social_watch_fn):
    """Register all scheduled jobs on the given scheduler.

    Args:
        scheduler: APScheduler instance
        pipeline_fn: callable(schedule_name) that runs the full fetch→push pipeline
        heartbeat_fn: callable() that sends heartbeat + checks source health
        defillama_sync_fn: callable() that refreshes DefiLlama candidate chains
    """
    # Grant + Hackathon — twice daily
    scheduler.add_job(
        lambda: pipeline_fn("grant_hackathon"),
        trigger=CronTrigger.from_crontab(GRANT_HACKATHON_SCHEDULE, timezone="Asia/Shanghai"),
        id="pipeline_grant_hackathon",
        name="Grant & Hackathon Pipeline",
        replace_existing=True,
    )

    # Bounty — every 2 hours
    scheduler.add_job(
        lambda: pipeline_fn("bounty"),
        trigger=CronTrigger.from_crontab(BOUNTY_SCHEDULE, timezone="Asia/Shanghai"),
        id="pipeline_bounty",
        name="Bounty Pipeline",
        replace_existing=True,
    )

    # Social watch — medium-frequency polling
    scheduler.add_job(
        social_watch_fn,
        trigger=_social_watch_trigger(),
        id="pipeline_social_watch",
        name="Twitter Social Watch Pipeline",
        replace_existing=True,
    )

    # Heartbeat + health check
    scheduler.add_job(
        heartbeat_fn,
        trigger=_heartbeat_trigger(),
        id="heartbeat",
        name="System Heartbeat & Health Check",
        replace_existing=True,
    )

    if settings.DEFILLAMA_SYNC_ENABLED:
        scheduler.add_job(
            defillama_sync_fn,
            trigger=CronTrigger.from_crontab(DEFILLAMA_SYNC_SCHEDULE, timezone="Asia/Shanghai"),
            id="defillama_candidate_sync",
            name="DefiLlama Candidate Sync",
            replace_existing=True,
        )

    logger.info(
        f"Registered jobs: grant_hackathon({GRANT_HACKATHON_SCHEDULE}), "
        f"bounty({BOUNTY_SCHEDULE}), heartbeat({HEARTBEAT_SCHEDULE}), "
        f"social_watch({settings.SOCIAL_WATCH_INTERVAL_MINUTES}m), "
        f"defillama_sync({'disabled' if not settings.DEFILLAMA_SYNC_ENABLED else DEFILLAMA_SYNC_SCHEDULE})"
    )
