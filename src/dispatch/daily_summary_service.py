"""Aggregate same-day pipeline outcomes for operator-facing Slack summaries."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from src.db.models import Event, EventSource, PushLog, ScheduleLog

SUMMARY_JOBS = {
    "pipeline_grant_hackathon",
    "pipeline_bounty",
    "pipeline_social_watch",
}


def _day_bounds(summary_date: dt.date) -> tuple[dt.datetime, dt.datetime]:
    tz = ZoneInfo("Asia/Shanghai")
    start_local = dt.datetime.combine(summary_date, dt.time.min, tzinfo=tz)
    end_local = start_local + dt.timedelta(days=1)
    start = start_local.astimezone(dt.timezone.utc)
    end = end_local.astimezone(dt.timezone.utc)
    return start, end


def build_daily_summary(db: Session, *, summary_date: dt.date) -> dict:
    start, end = _day_bounds(summary_date)

    logs = (
        db.query(ScheduleLog)
        .filter(
            ScheduleLog.job_name.in_(SUMMARY_JOBS),
            ScheduleLog.started_at >= start,
            ScheduleLog.started_at < end,
        )
        .all()
    )

    totals = {
        "fetched": sum(log.items_fetched or 0 for log in logs),
        "new": sum(log.items_new or 0 for log in logs),
        "deduped": sum(log.items_deduped or 0 for log in logs),
        "classified": sum(log.items_classified or 0 for log in logs),
        "verified": sum(log.items_verified or 0 for log in logs),
        "pushed": db.query(PushLog)
        .filter(PushLog.pushed_at >= start, PushLog.pushed_at < end, PushLog.success == True)
        .count(),
    }

    events = (
        db.query(Event)
        .filter(Event.created_at >= start, Event.created_at < end)
        .order_by(Event.created_at.asc())
        .all()
    )

    event_ids = [event.id for event in events]
    event_sources = []
    if event_ids:
        event_sources = (
            db.query(EventSource)
            .filter(EventSource.event_id.in_(event_ids))
            .order_by(EventSource.event_id.asc(), EventSource.fetched_at.asc(), EventSource.id.asc())
            .all()
        )

    source_names = sorted({source.source_name for source in event_sources if source.source_name})
    primary_sources_by_event_id = {}
    for source in event_sources:
        primary_sources_by_event_id.setdefault(source.event_id, source)

    return {
        "summary_date": summary_date.isoformat(),
        "totals": totals,
        "new_events_count": len(events),
        "new_event_sources": source_names,
        "new_events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "title": event.title,
                "ecosystem": event.ecosystem,
                "final_score": event.final_score,
                "status": event.status,
                "source_type": (
                    primary_sources_by_event_id[event.id].source_type
                    if event.id in primary_sources_by_event_id else ""
                ),
                "source_name": (
                    primary_sources_by_event_id[event.id].source_name
                    if event.id in primary_sources_by_event_id else ""
                ),
                "source_url": (
                    primary_sources_by_event_id[event.id].source_url or event.source_url or ""
                    if event.id in primary_sources_by_event_id else (event.source_url or "")
                ),
                "application_url": event.application_url,
            }
            for event in events
        ],
    }