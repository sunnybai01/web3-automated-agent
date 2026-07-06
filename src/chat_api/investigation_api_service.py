from src.agent.investigation_service import investigate_event
from src.db.database import SessionLocal


def investigate_event_by_id(event_id: int) -> dict:
    db = SessionLocal()
    try:
        return investigate_event(db, event_id)
    finally:
        db.close()