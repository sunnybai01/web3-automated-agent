"""APScheduler job definitions — split frequency for Grant/Hackathon vs Bounty."""
import logging
from datetime import datetime
from typing import Dict, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings

logger = logging.getLogger(__name__)

# Schedule definitions
GRANT_HACKATHON_SCHEDULE = "0 9,21 * * *"   # 09:00, 21:00 daily
BOUNTY_SCHEDULE = "0 */2 * * *"              # every 2 hours
HEARTBEAT_SCHEDULE = f"*/{settings.HEARTBEAT_INTERVAL_MINUTES} * * * *"


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    return scheduler


def register_jobs(scheduler: BackgroundScheduler, pipeline_fn, heartbeat_fn):
    """Register all scheduled jobs on the given scheduler.

    Args:
        scheduler: APScheduler instance
        pipeline_fn: callable(schedule_name) that runs the full fetch→push pipeline
        heartbeat_fn: callable() that sends heartbeat + checks source health
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

    # Heartbeat + health check
    scheduler.add_job(
        heartbeat_fn,
        trigger=CronTrigger.from_crontab(HEARTBEAT_SCHEDULE, timezone="Asia/Shanghai"),
        id="heartbeat",
        name="System Heartbeat & Health Check",
        replace_existing=True,
    )

    logger.info(
        f"Registered jobs: grant_hackathon({GRANT_HACKATHON_SCHEDULE}), "
        f"bounty({BOUNTY_SCHEDULE}), heartbeat({HEARTBEAT_SCHEDULE})"
    )
