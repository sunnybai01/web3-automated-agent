import datetime
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.db.database import Base
from src.db.models import Event, EventSource, PushLog, ScheduleLog
from src.dispatch.daily_summary_service import build_daily_summary


def _db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[Event.__table__, EventSource.__table__, PushLog.__table__, ScheduleLog.__table__],
    )
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def test_build_daily_summary_includes_totals_and_new_event_sources() -> None:
    db = _db_session()
    try:
        summary_date = datetime.date(2026, 7, 6)

        db.add_all(
            [
                ScheduleLog(
                    job_name="pipeline_grant_hackathon",
                    status="success",
                    started_at=datetime.datetime(2026, 7, 6, 1, 0),
                    items_fetched=10,
                    items_new=1,
                    items_deduped=5,
                    items_classified=3,
                    items_verified=1,
                ),
                ScheduleLog(
                    job_name="pipeline_bounty",
                    status="success",
                    started_at=datetime.datetime(2026, 7, 6, 2, 0),
                    items_fetched=20,
                    items_new=0,
                    items_deduped=12,
                    items_classified=4,
                    items_verified=1,
                ),
                ScheduleLog(
                    job_name="pipeline_social_watch",
                    status="success",
                    started_at=datetime.datetime(2026, 7, 6, 3, 0),
                    items_fetched=30,
                    items_new=1,
                    items_deduped=18,
                    items_classified=6,
                    items_verified=2,
                ),
            ]
        )
        db.commit()

        event = Event(
            event_type="grant",
            title="Base Builder Rewards",
            description="Funding opportunity.",
            ecosystem="base",
            final_score=7.8,
            created_at=datetime.datetime(2026, 7, 6, 4, 0),
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        db.add(
            EventSource(
                event_id=event.id,
                source_type="twitter",
                source_name="twitter_buildonbase",
                source_url="https://x.com/buildonbase/status/1",
            )
        )
        db.commit()

        payload = build_daily_summary(db, summary_date=summary_date)

        assert payload["summary_date"] == "2026-07-06"
        assert payload["totals"]["fetched"] == 60
        assert payload["totals"]["new"] == 2
        assert payload["new_events_count"] == 1
        assert payload["new_event_sources"] == ["twitter_buildonbase"]
        assert payload["new_events"][0]["title"] == "Base Builder Rewards"
        assert payload["new_events"][0]["source_type"] == "twitter"
        assert payload["new_events"][0]["source_url"] == "https://x.com/buildonbase/status/1"
    finally:
        db.close()


def test_build_daily_summary_handles_empty_new_events() -> None:
    db = _db_session()
    try:
        summary_date = datetime.date(2026, 7, 6)

        db.add(
            ScheduleLog(
                job_name="pipeline_social_watch",
                status="success",
                started_at=datetime.datetime(2026, 7, 6, 3, 0),
                items_fetched=30,
                items_new=0,
                items_deduped=30,
                items_classified=0,
                items_verified=0,
            )
        )
        db.commit()

        payload = build_daily_summary(db, summary_date=summary_date)

        assert payload["totals"]["fetched"] == 30
        assert payload["new_events_count"] == 0
        assert payload["new_event_sources"] == []
        assert payload["new_events"] == []
    finally:
        db.close()