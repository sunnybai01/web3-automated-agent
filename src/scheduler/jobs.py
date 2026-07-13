"""APScheduler job definitions for grant, hackathon, and social watch pipelines."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import settings

logger = logging.getLogger(__name__)

# Schedule definitions
GRANT_HACKATHON_SCHEDULE = "0 9 * * *"   # 09:00 daily
HEARTBEAT_SCHEDULE = f"*/{settings.HEARTBEAT_INTERVAL_MINUTES} * * * *"
DAILY_SUMMARY_SCHEDULE = settings.DAILY_SUMMARY_CRON
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


def register_jobs(scheduler: BackgroundScheduler, pipeline_fn, heartbeat_fn, social_watch_fn, daily_summary_fn):
    """Register all scheduled jobs on the given scheduler.

    Args:
        scheduler: APScheduler instance
        pipeline_fn: callable(schedule_name) that runs the full fetch→push pipeline
        heartbeat_fn: callable() that sends heartbeat + checks source health
        social_watch_fn: callable() that runs the social watch pipeline
        daily_summary_fn: callable() that builds and sends the daily summary
    """
    # Grant + Hackathon — once daily
    scheduler.add_job(
        lambda: pipeline_fn("grant_hackathon"),
        trigger=CronTrigger.from_crontab(GRANT_HACKATHON_SCHEDULE, timezone="Asia/Shanghai"),
        id="pipeline_grant_hackathon",
        name="Grant & Hackathon Pipeline",
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

    if settings.DAILY_SUMMARY_ENABLED:
        scheduler.add_job(
            daily_summary_fn,
            trigger=CronTrigger.from_crontab(DAILY_SUMMARY_SCHEDULE, timezone="Asia/Shanghai"),
            id="daily_slack_summary",
            name="Daily Slack Summary",
            replace_existing=True,
        )

    logger.info(
        f"Registered jobs: grant_hackathon({GRANT_HACKATHON_SCHEDULE}), "
        f"heartbeat({HEARTBEAT_SCHEDULE}), "
        f"social_watch({settings.SOCIAL_WATCH_INTERVAL_MINUTES}m), "
        f"daily_summary({'disabled' if not settings.DAILY_SUMMARY_ENABLED else DAILY_SUMMARY_SCHEDULE})"
    )
