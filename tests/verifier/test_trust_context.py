import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.verifier.verifier import verify_opportunity


def test_verify_opportunity_l1_failure_degrades_but_does_not_reject_official_source(monkeypatch) -> None:
    """Official metadata no longer overrides L1 — L1 only degrades confidence.
    Only L3 (security APIs) can reject as fraud."""
    monkeypatch.setattr(
        "src.verifier.verifier.origin_check",
        lambda source_url, source_name: {"passed": False, "reason": "domain not in global whitelist"},
    )
    monkeypatch.setattr(
        "src.verifier.verifier.cross_reference_check",
        lambda event_type, application_url, source_url, metadata: {"passed": True, "reason": "matched"},
    )
    monkeypatch.setattr(
        "src.verifier.verifier.security_api_check",
        lambda check_url: {"passed": True, "reason": "clean"},
    )

    result = verify_opportunity(
        event_type="grant",
        source_url="https://grants.base.org/programs",
        application_url="https://apply.base.org/grant",
        source_name="base_grants",
        metadata={
            "chain": "base",
            "source_tier": "official",
            "official": True,
            "signal_type": "grant",
        },
    )

    assert result["is_verified"] is True  # L3 passed → not fraud
    assert result["verdict"] == "degraded"  # L1 failed → degraded, not verified
    assert result["verification_log"]["source_context"] == {
        "chain": "base",
        "source_tier": "official",
        "official": True,
        "signal_type": "grant",
    }
    assert result["verification_log"]["layers"]["origin_anchor"]["passed"] is False


def test_verify_opportunity_l3_failure_still_rejects_as_fraud(monkeypatch) -> None:
    """L3 (security API) is the only hard gate — phishing/malware = fraud."""
    monkeypatch.setattr(
        "src.verifier.verifier.origin_check",
        lambda source_url, source_name: {"passed": True, "reason": "domain_match:base.org"},
    )
    monkeypatch.setattr(
        "src.verifier.verifier.cross_reference_check",
        lambda event_type, application_url, source_url, metadata: {"passed": True, "reason": "matched"},
    )
    monkeypatch.setattr(
        "src.verifier.verifier.security_api_check",
        lambda check_url: {"passed": False, "reason": "phishing_detected"},
    )

    result = verify_opportunity(
        event_type="grant",
        source_url="https://fake-grants.scam/phish",
        application_url="https://fake-grants.scam/apply",
        source_name="unknown",
    )

    assert result["is_verified"] is False
    assert result["verdict"] == "fraud"
