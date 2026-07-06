from datetime import datetime, timedelta, timezone


def _source_trust_from_event(event) -> str:
    log = event.verification_log or {}
    source_context = log.get("source_context") or {}
    source_tier = str(source_context.get("source_tier") or "").lower()
    official = bool(source_context.get("official", source_tier == "official"))
    return "official" if official else "discovery"


def _verification_verdict_from_event(event) -> str:
    log = event.verification_log or {}
    return str(log.get("verdict") or "unknown")


def list_opportunities(filters: dict) -> dict:
    from sqlalchemy import desc

    from src.db.database import SessionLocal
    from src.db.models import Event

    event_types = filters.get("event_types") or ["grant", "hackathon", "bounty"]
    ecosystem = (filters.get("ecosystem") or "").strip()
    min_score = float(filters.get("min_score", 5.0))
    days = int(filters.get("days", 14))
    source_trust = str(filters.get("source_trust") or "all").strip().lower()

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = db.query(Event).filter(
            Event.created_at >= cutoff,
            Event.status.in_(["new", "pushed"]),
            Event.final_score >= min_score,
        )

        if event_types:
            query = query.filter(Event.event_type.in_(event_types))
        if ecosystem:
            query = query.filter(Event.ecosystem.ilike(f"%{ecosystem}%"))

        events = query.order_by(desc(Event.final_score)).limit(200).all()

        if source_trust in {"official", "discovery"}:
            events = [
                event for event in events if _source_trust_from_event(event) == source_trust
            ]

        items = []
        for event in events:
            trust = _source_trust_from_event(event)
            verification_verdict = _verification_verdict_from_event(event)
            items.append(
                {
                    "id": event.id,
                    "score": round(event.final_score, 1) if event.final_score is not None else None,
                    "type": (event.event_type or "").upper(),
                    "title": (event.title or "")[:120],
                    "ecosystem": event.ecosystem or "-",
                    "amount": event.amount or "-",
                    "deadline": event.deadline.strftime("%Y-%m-%d") if event.deadline else "Rolling",
                    "heat": event.heat_count or 1,
                    "verified": bool(event.is_verified),
                    "source_trust": trust,
                    "verification_verdict": verification_verdict,
                    "apply_url": event.application_url or event.source_url or "",
                }
            )

        total = len(events)
        avg_score = round(sum((event.final_score or 0) for event in events) / max(total, 1), 1)
        verified_percent = int(round(sum(1 for event in events if event.is_verified) / max(total, 1) * 100))

        return {
            "metrics": {
                "total_shown": total,
                "avg_score": avg_score,
                "verified_percent": verified_percent,
                "grants": sum(1 for event in events if event.event_type == "grant"),
                "bounties": sum(1 for event in events if event.event_type == "bounty"),
                "hackathons": sum(1 for event in events if event.event_type == "hackathon"),
                "official": sum(1 for event in events if _source_trust_from_event(event) == "official"),
                "discovery": sum(1 for event in events if _source_trust_from_event(event) == "discovery"),
            },
            "items": items,
        }
    finally:
        db.close()


def _format_dt(value: datetime | None, fmt: str, fallback: str = "") -> str:
    if not value:
        return fallback
    return value.strftime(fmt)


def list_source_health() -> dict:
    from src.db.database import SessionLocal
    from src.db.models import SourceHealth

    db = SessionLocal()
    try:
        sources = db.query(SourceHealth).order_by(SourceHealth.source_name.asc()).all()

        items = [
            {
                "source": source.source_name,
                "status": source.status or "unknown",
                "last_success": _format_dt(source.last_success_at, "%Y-%m-%d %H:%M", "Never"),
                "last_fetch": _format_dt(source.last_fetch_at, "%Y-%m-%d %H:%M", "Never"),
                "failures": source.consecutive_failures or 0,
                "last_error": (source.last_error or "")[:100],
            }
            for source in sources
        ]

        return {
            "summary": {
                "total_sources": len(sources),
                "healthy": sum(1 for source in sources if source.status == "healthy"),
                "degraded": sum(1 for source in sources if source.status == "degraded"),
                "down": sum(1 for source in sources if source.status == "down"),
            },
            "items": items,
        }
    finally:
        db.close()


def list_schedule_logs(limit: int = 50) -> dict:
    from sqlalchemy import desc

    from src.db.database import SessionLocal
    from src.db.models import ScheduleLog

    db = SessionLocal()
    try:
        logs = db.query(ScheduleLog).order_by(desc(ScheduleLog.started_at)).limit(limit).all()

        items = [
            {
                "id": log.id,
                "job": log.job_name,
                "status": log.status or "unknown",
                "started": _format_dt(log.started_at, "%m-%d %H:%M"),
                "fetched": log.items_fetched or 0,
                "new": log.items_new or 0,
                "deduped": log.items_deduped or 0,
                "classified": log.items_classified or 0,
                "verified": log.items_verified or 0,
                "error": (log.error_message or "")[:80],
            }
            for log in logs
        ]

        return {
            "summary": {
                "total_runs": len(logs),
                "success": sum(1 for log in logs if log.status == "success"),
                "failed": sum(1 for log in logs if log.status == "failed"),
                "running": sum(1 for log in logs if log.status == "running"),
            },
            "items": items,
        }
    finally:
        db.close()


def list_investigations(limit: int = 50) -> dict:
    from sqlalchemy import desc

    from src.db.database import SessionLocal
    from src.db.models import AgentMission

    db = SessionLocal()
    try:
        missions = db.query(AgentMission).order_by(desc(AgentMission.started_at)).limit(limit).all()

        items = []
        for mission in missions:
            conclusion = mission.conclusion or {}
            similar_events = conclusion.get("similar_events") or []
            supporting_evidence = conclusion.get("supporting_evidence") or None
            items.append(
                {
                    "mission_id": mission.id,
                    "event_id": mission.event_id,
                    "status": mission.status or "unknown",
                    "started": _format_dt(mission.started_at, "%m-%d %H:%M"),
                    "finished": _format_dt(mission.finished_at, "%m-%d %H:%M"),
                    "title": str(conclusion.get("title") or ""),
                    "verdict": str(conclusion.get("verdict") or "unknown"),
                    "recommended_action": str(conclusion.get("recommended_action") or ""),
                    "similar_count": len(similar_events),
                    "has_supporting_evidence": bool(supporting_evidence),
                    "error": (mission.error_message or "")[:80],
                }
            )

        return {
            "summary": {
                "total_runs": len(missions),
                "completed": sum(1 for mission in missions if mission.status == "completed"),
                "failed": sum(1 for mission in missions if mission.status == "failed"),
                "running": sum(1 for mission in missions if mission.status == "running"),
            },
            "items": items,
        }
    finally:
        db.close()