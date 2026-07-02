import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.classifier.scorer import OpportunityScorer


class NullLLM:
    def classify_structured(self, system_prompt, user_prompt):
        return None


def _base_event() -> dict:
    return {
        "event_type": "GRANT",
        "title": "Protocol Growth Grants",
        "description": "Funding for infrastructure teams.",
        "amount": "$25,000",
        "ecosystem": "emerging",
        "track": "Infra",
        "source_platform": "custom",
    }


def test_official_sources_score_higher_than_discovery_sources() -> None:
    scorer = OpportunityScorer(NullLLM())

    official = scorer.score(
        {
            **_base_event(),
            "source_tier": "official",
            "official": True,
            "verification_verdict": "verified",
        }
    )
    discovery = scorer.score(
        {
            **_base_event(),
            "source_tier": "discovery",
            "official": False,
            "verification_verdict": "degraded",
        }
    )

    assert official is not None
    assert discovery is not None
    assert official["score_reputation"] > discovery["score_reputation"]
    assert official["final_score"] > discovery["final_score"]
