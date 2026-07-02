import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.verifier.verifier import verify_opportunity


def test_verify_opportunity_uses_official_source_metadata_to_override_origin_failure(monkeypatch) -> None:
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

    assert result["is_verified"] is True
    assert result["verdict"] == "verified"
    assert result["verification_log"]["source_context"] == {
        "chain": "base",
        "source_tier": "official",
        "official": True,
        "signal_type": "grant",
    }
    assert result["verification_log"]["layers"]["origin_anchor"]["overridden"] is True
