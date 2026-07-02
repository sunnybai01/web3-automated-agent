"""System heartbeat and source health monitoring."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from sqlalchemy.orm import Session

from src.db.queries import get_unhealthy_sources
from src.db.database import SessionLocal

logger = logging.getLogger(__name__)

# Track daily stats in memory (per-process)
_daily_stats: Dict[str, int] = {
    "fetched": 0,
    "new": 0,
    "deduped": 0,
    "pushed": 0,
    "verified": 0,
    "fraud": 0,
}


def heartbeat(slack_send_fn) -> dict:
    """Run heartbeat: check source health, compile stats, push to Slack.

    Returns the stats dict.
    """
    db: Session = SessionLocal()
    try:
        unhealthy = get_unhealthy_sources(db)
        stats = {
            **_daily_stats,
            "unhealthy": len(unhealthy),
            "unhealthy_names": [s.source_name for s in unhealthy],
        }

        return stats
    finally:
        db.close()


def increment_stat(key: str, amount: int = 1):
    if key in _daily_stats:
        _daily_stats[key] += amount


def reset_daily_stats():
    for key in _daily_stats:
        _daily_stats[key] = 0
