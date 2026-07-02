from typing import Literal


ReliabilityLevel = Literal["low", "medium", "high"]
ReliabilityVerdict = Literal["untrusted", "caution", "trusted"]


def map_score_to_level(score: int) -> ReliabilityLevel:
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def map_level_to_verdict(
    level: ReliabilityLevel,
    *,
    has_major_conflict: bool,
    critical_security_failure: bool,
) -> ReliabilityVerdict:
    if critical_security_failure:
        return "untrusted"
    if level == "high" and not has_major_conflict:
        return "trusted"
    if level == "low":
        return "untrusted"
    return "caution"


def compute_reliability(
    *,
    origin: int,
    completeness: int,
    consistency: int,
    cross_reference: int,
    security_penalty: int,
    history_bonus: int,
    has_cross_reference: bool,
    has_major_conflict: bool,
    critical_security_failure: bool = False,
) -> dict[str, int | str]:
    raw_score = (
        origin
        + completeness
        + consistency
        + cross_reference
        + security_penalty
        + history_bonus
    )
    score = max(0, min(100, raw_score))

    if not has_cross_reference:
        score = min(score, 80)

    level = map_score_to_level(score)
    if not has_cross_reference and level == "high":
        level = "medium"

    verdict = map_level_to_verdict(
        level,
        has_major_conflict=has_major_conflict,
        critical_security_failure=critical_security_failure,
    )

    return {"score": score, "level": level, "verdict": verdict}