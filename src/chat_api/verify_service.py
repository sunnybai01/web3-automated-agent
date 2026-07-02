from src.chat_api.scoring import compute_reliability


def verify_targets(target_ids: list[int]) -> dict:
    from sqlalchemy import select

    from src.db.database import SessionLocal
    from src.db.models import Event
    from src.verifier.verifier import verify_opportunity

    db = SessionLocal()
    try:
        stmt = select(Event).where(Event.id.in_(target_ids)).limit(1)
        event = db.execute(stmt).scalar_one_or_none()
        if event is None:
            return {
                "score": 0,
                "level": "low",
                "verdict": "untrusted",
                "evidence": [],
                "unknowns": ["event not found"],
                "conflicts": [],
            }

        check = verify_opportunity(
            event_type=(event.event_type or "").upper(),
            source_url=event.source_url or "",
            application_url=event.application_url or "",
            source_name=event.source_platform or "",
        )

        layers = check.get("verification_log", {}).get("layers", {})
        l1 = layers.get("origin_anchor", {})
        l2 = layers.get("cross_reference", {})
        l3 = layers.get("security_api", {})

        evidence = [
            {
                "category": "origin",
                "detail": l1.get("reason", "origin unknown"),
                "source": "verifier_layer",
                "weight": 25,
                "impact": "positive" if l1.get("passed") else "negative",
            },
            {
                "category": "cross_reference",
                "detail": l2.get("reason", "cross reference unknown"),
                "source": "verifier_layer",
                "weight": 25,
                "impact": "positive" if l2.get("passed") else "negative",
            },
            {
                "category": "security",
                "detail": l3.get("reason", "security unknown"),
                "source": "verifier_layer",
                "weight": 20,
                "impact": "positive" if l3.get("passed") else "negative",
            },
        ]

        reliability = compute_reliability(
            origin=25 if l1.get("passed") else 0,
            completeness=15 if event.title and event.amount and event.deadline else 5,
            consistency=20 if event.title and (event.source_url or event.application_url) else 5,
            cross_reference=25 if l2.get("passed") else 0,
            security_penalty=0 if l3.get("passed") else -20,
            history_bonus=10 if event.heat_count and event.heat_count >= 2 else 0,
            has_cross_reference=bool(l2.get("passed")),
            has_major_conflict=check.get("verdict") == "fraud",
            critical_security_failure=not bool(l3.get("passed")),
        )

        unknowns = []
        if not event.amount:
            unknowns.append("missing amount")
        if not event.deadline:
            unknowns.append("missing deadline")

        conflicts = []
        if check.get("verdict") == "fraud":
            conflicts.append("verifier flagged fraud verdict")

        return {
            **reliability,
            "evidence": evidence,
            "unknowns": unknowns,
            "conflicts": conflicts,
        }
    finally:
        db.close()