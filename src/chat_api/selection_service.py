def select_target_event_ids(params: dict) -> list[int]:
    event_id = params.get("event_id")
    if event_id is not None:
        return [int(event_id)]

    source_name = params.get("source_name")
    from_dt = params.get("from")
    to_dt = params.get("to")
    limit = min(max(int(params.get("limit", 20)), 1), 100)

    if not source_name or not from_dt or not to_dt:
        return []

    from sqlalchemy import select

    from src.db.database import SessionLocal
    from src.db.models import Event, EventSource

    db = SessionLocal()
    try:
        stmt = (
            select(Event.id)
            .join(EventSource, EventSource.event_id == Event.id)
            .where(EventSource.source_name == source_name)
            .where(Event.created_at >= from_dt)
            .where(Event.created_at <= to_dt)
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        return [row[0] for row in db.execute(stmt).all()]
    finally:
        db.close()
