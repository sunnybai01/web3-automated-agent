"""Common database queries."""
import datetime
from typing import Optional, List

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from .models import RawSignal, Event, EventSource, SourceHealth, TwitterSourceState, ScheduleLog, PushLog


# --- RawSignal ---

def insert_raw_signal(db: Session, **kwargs) -> Optional[RawSignal]:
    try:
        signal = RawSignal(**kwargs)
        db.add(signal)
        db.commit()
        db.refresh(signal)
        return signal
    except Exception:
        db.rollback()
        return None


def canonical_url_exists(db: Session, canonical_url: str) -> bool:
    return db.query(
        db.query(RawSignal).filter(RawSignal.canonical_url == canonical_url).exists()
    ).scalar()


# --- Event ---

def insert_event(db: Session, **kwargs) -> Event:
    event = Event(**kwargs)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event(db: Session, event_id: int, **kwargs) -> Optional[Event]:
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        return None
    for key, value in kwargs.items():
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return event


def get_event_by_id(db: Session, event_id: int) -> Optional[Event]:
    return db.query(Event).filter(Event.id == event_id).first()


def get_recent_events(
    db: Session,
    event_type: Optional[str] = None,
    ecosystem: Optional[str] = None,
    min_score: Optional[float] = None,
    limit: int = 50,
) -> List[Event]:
    q = db.query(Event)
    if event_type:
        q = q.filter(Event.event_type == event_type)
    if ecosystem:
        q = q.filter(Event.ecosystem == ecosystem)
    if min_score is not None:
        q = q.filter(Event.final_score >= min_score)
    return q.order_by(Event.created_at.desc()).limit(limit).all()


def get_events_in_window(
    db: Session,
    window_days: int = 14,
) -> List[Event]:
    """Get events within the sliding window for dedup comparison."""
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=window_days)
    return db.query(Event).filter(Event.created_at >= cutoff).all()


def expire_event(db: Session, event_id: int) -> Optional[Event]:
    return update_event(db, event_id, status="expired")


def mark_event_fraud(db: Session, event_id: int, log: dict) -> Optional[Event]:
    return update_event(db, event_id, status="fraud", verification_log=log, is_verified=False)


# --- EventSource ---

def add_event_source(db: Session, event_id: int, source_type: str,
                     source_name: str, source_url: Optional[str] = None,
                     raw_signal_id: Optional[int] = None) -> EventSource:
    es = EventSource(
        event_id=event_id,
        source_type=source_type,
        source_name=source_name,
        source_url=source_url,
        raw_signal_id=raw_signal_id,
    )
    db.add(es)
    db.commit()
    db.refresh(es)
    return es


def get_event_source_count(db: Session, event_id: int) -> int:
    return db.query(EventSource).filter(EventSource.event_id == event_id).count()


# --- SourceHealth ---

def upsert_source_health(db: Session, source_name: str, success: bool = True,
                         error: Optional[str] = None):
    sh = db.query(SourceHealth).filter(SourceHealth.source_name == source_name).first()
    now = datetime.datetime.now(datetime.timezone.utc)
    if not sh:
        sh = SourceHealth(source_name=source_name)
        db.add(sh)

    sh.last_fetch_at = now
    if success:
        sh.last_success_at = now
        sh.consecutive_failures = 0
        sh.status = "healthy"
        sh.last_error = None
    else:
        sh.consecutive_failures = (sh.consecutive_failures or 0) + 1
        sh.last_error = error
        if sh.consecutive_failures >= 3:
            sh.status = "down"
        elif sh.consecutive_failures >= 1:
            sh.status = "degraded"
    db.commit()


def get_source_health(db: Session, source_name: str) -> Optional[SourceHealth]:
    return db.query(SourceHealth).filter(SourceHealth.source_name == source_name).first()


def get_unhealthy_sources(db: Session) -> List[SourceHealth]:
    return db.query(SourceHealth).filter(SourceHealth.status != "healthy").all()


def get_twitter_source_state(db: Session, source_name: str) -> Optional[TwitterSourceState]:
    return db.query(TwitterSourceState).filter(
        TwitterSourceState.source_name == source_name
    ).first()


def upsert_twitter_source_state(
    db: Session,
    source_name: str,
    **kwargs,
) -> TwitterSourceState:
    state = get_twitter_source_state(db, source_name)
    if state is None:
        state = TwitterSourceState(source_name=source_name)
        db.add(state)

    for key, value in kwargs.items():
        setattr(state, key, value)

    db.commit()
    db.refresh(state)
    return state


# --- ScheduleLog ---

def create_schedule_log(db: Session, job_name: str) -> ScheduleLog:
    log = ScheduleLog(job_name=job_name, status="running")
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def finish_schedule_log(db: Session, log_id: int, items_fetched: int = 0,
                        items_new: int = 0, items_deduped: int = 0,
                        items_classified: int = 0, items_verified: int = 0,
                        error: Optional[str] = None):
    log = db.query(ScheduleLog).filter(ScheduleLog.id == log_id).first()
    if log:
        log.status = "failed" if error else "success"
        log.error_message = error
        log.items_fetched = items_fetched
        log.items_new = items_new
        log.items_deduped = items_deduped
        log.items_classified = items_classified
        log.items_verified = items_verified
        log.finished_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()


# --- PushLog ---

def create_push_log(db: Session, event_id: int, action: str = "create",
                    slack_ts: Optional[str] = None, success: bool = True,
                    error_message: Optional[str] = None) -> PushLog:
    pl = PushLog(
        event_id=event_id,
        action=action,
        slack_ts=slack_ts,
        success=success,
        error_message=error_message,
    )
    db.add(pl)
    db.commit()
    db.refresh(pl)
    return pl


def get_push_log_for_event(db: Session, event_id: int) -> Optional[PushLog]:
    return db.query(PushLog).filter(
        PushLog.event_id == event_id,
        PushLog.action == "create",
        PushLog.success == True,
    ).first()
