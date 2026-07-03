import datetime
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.db.database import Base
from src.db.models import TwitterSourceState
from src.db.queries import get_twitter_source_state, upsert_twitter_source_state


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[TwitterSourceState.__table__])
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_upsert_twitter_source_state_creates_and_updates_record(db_session) -> None:
    state = upsert_twitter_source_state(
        db_session,
        source_name="twitter_base",
        last_tweet_id="123",
        cursor="CURSOR_A",
        auth_profile="primary",
    )

    assert state.source_name == "twitter_base"
    assert state.last_tweet_id == "123"
    assert state.cursor == "CURSOR_A"

    state = upsert_twitter_source_state(
        db_session,
        source_name="twitter_base",
        last_tweet_id="456",
        cursor="CURSOR_B",
        auth_profile="primary",
    )

    assert state.last_tweet_id == "456"
    assert state.cursor == "CURSOR_B"


def test_twitter_source_state_supports_cooldown_window(db_session) -> None:
    cooldown_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=20)
    upsert_twitter_source_state(
        db_session,
        source_name="twitter_list_alpha",
        cooldown_until=cooldown_until,
    )

    state = get_twitter_source_state(db_session, "twitter_list_alpha")

    assert state is not None
    assert state.cooldown_until == cooldown_until.replace(tzinfo=None)