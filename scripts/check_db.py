#!/usr/bin/env python3
"""Check database state for dedup/ staleness audit."""
from src.db.database import SessionLocal
from src.db.models import RawSignal, Event
from sqlalchemy import func

db = SessionLocal()

print("=== raw_signals by source ===")
results = (
    db.query(
        RawSignal.source_name,
        func.count(RawSignal.id),
        func.min(RawSignal.fetched_at),
        func.max(RawSignal.fetched_at),
    )
    .group_by(RawSignal.source_name)
    .order_by(func.count(RawSignal.id).desc())
    .limit(30)
    .all()
)
for r in results:
    print(f"  {r[0]:45s} count={r[1]:5d}  {str(r[2])[:19] if r[2] else 'N/A'} ~ {str(r[3])[:19] if r[3] else 'N/A'}")

total_raw = db.query(RawSignal).count()
total_events = db.query(Event).count()
print(f"\n  TOTAL raw_signals: {total_raw}")
print(f"  TOTAL events: {total_events}")

print("\n=== events by status ===")
for status, cnt in (
    db.query(Event.status, func.count(Event.id))
    .group_by(Event.status)
    .all()
):
    print(f"  {status}: {cnt}")

print("\n=== events by event_type ===")
for etype, cnt in (
    db.query(Event.event_type, func.count(Event.id))
    .group_by(Event.event_type)
    .all()
):
    print(f"  {etype}: {cnt}")

db.close()
