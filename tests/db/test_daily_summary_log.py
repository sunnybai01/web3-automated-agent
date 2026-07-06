import datetime
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.db.database import Base
from src.db.models import DailySummaryLog
from src.db.queries import (
    create_daily_summary_log,
    get_daily_summary_log,
    mark_daily_summary_sent,
)


def _db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[DailySummaryLog.__table__])
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def test_daily_summary_log_create_lookup_and_mark_sent() -> None:
    db = _db_session()
    try:
        summary_date = datetime.date(2026, 7, 6)

        row = create_daily_summary_log(db, summary_date=summary_date, channel="slack")

        assert row.summary_date == summary_date
        assert row.channel == "slack"
        assert row.status == "running"

        loaded = get_daily_summary_log(db, summary_date=summary_date, channel="slack")
        assert loaded is not None
        assert loaded.id == row.id

        marked = mark_daily_summary_sent(db, row.id, slack_ts="123.456")
        assert marked is not None
        assert marked.status == "success"
        assert marked.slack_ts == "123.456"
    finally:
        db.close()