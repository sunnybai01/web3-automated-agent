import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.chat_api.scoring import compute_reliability, map_score_to_level


def test_score_is_clamped_to_0_100() -> None:
    result = compute_reliability(
        origin=30,
        completeness=30,
        consistency=30,
        cross_reference=30,
        security_penalty=0,
        history_bonus=20,
        has_cross_reference=True,
        has_major_conflict=False,
    )
    assert result["score"] == 100


def test_level_mapping_boundaries() -> None:
    assert map_score_to_level(54) == "low"
    assert map_score_to_level(55) == "medium"
    assert map_score_to_level(79) == "medium"
    assert map_score_to_level(80) == "high"


def test_high_requires_cross_reference() -> None:
    result = compute_reliability(
        origin=25,
        completeness=15,
        consistency=20,
        cross_reference=0,
        security_penalty=0,
        history_bonus=20,
        has_cross_reference=False,
        has_major_conflict=False,
    )
    assert result["score"] <= 80
    assert result["level"] != "high"