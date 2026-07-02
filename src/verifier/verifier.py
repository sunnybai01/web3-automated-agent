"""Zero-trust verification orchestrator — runs all three layers sequentially.

Each layer is a gate:
- Layer 1 fails → immediate rejection (fraud)
- Layer 2 fails → degraded (logged but may still pass with warning)
- Layer 3 fails → immediate rejection (fraud)

A verification is only "fully verified" if all three layers pass.
"""
import logging
from typing import Dict, Any

from .whitelist import origin_check
from .cross_reference import cross_reference_check
from .security_api import security_api_check

logger = logging.getLogger(__name__)


def _build_source_context(metadata: dict | None) -> Dict[str, Any]:
    metadata = metadata or {}
    source_tier = metadata.get("source_tier")
    official = bool(metadata.get("official", source_tier == "official"))
    return {
        "chain": metadata.get("chain"),
        "source_tier": source_tier,
        "official": official,
        "signal_type": metadata.get("signal_type"),
    }


class Verifier:
    """Runs the three-layer zero-trust verification pipeline.

    Usage:
        v = Verifier()
        result = v.verify(event_type="BOUNTY", source_url="...", application_url="...")
        if result["is_verified"]:
            # proceed to scoring
    """

    def verify(
        self,
        event_type: str,
        source_url: str = "",
        application_url: str = "",
        source_name: str = "",
        metadata: dict = None,
    ) -> Dict[str, Any]:
        """Run the full verification pipeline.

        Returns a dict with:
          - is_verified: bool
          - verification_log: dict with per-layer results
          - verdict: "verified" | "degraded" | "fraud"
        """
        verification_log = {
            "layers": {},
            "verdict": "degraded",
        }
        source_context = _build_source_context(metadata)
        verification_log["source_context"] = source_context

        # ---- Layer 1: Origin Identity Anchoring ----
        l1 = origin_check(source_url, source_name)
        verification_log["layers"]["origin_anchor"] = l1

        if not l1["passed"]:
            # Layer 1 failure = immediate fraud classification
            # UNLESS the source is a well-known platform (e.g., RSS feed itself is trusted)
            is_registry_official = source_context.get("official") or source_context.get("source_tier") == "official"
            if "immunefi.com" in source_url or "gitcoin.co" in source_url:
                # Known platforms get a pass on L1 when the URL comes from their own domain
                verification_log["layers"]["origin_anchor"]["overridden"] = True
                verification_log["layers"]["origin_anchor"]["passed"] = True
                verification_log["layers"]["origin_anchor"]["reason"] = (
                    f"{l1.get('reason', 'origin failed')}; overridden by trusted platform allowlist"
                )
            elif is_registry_official:
                verification_log["layers"]["origin_anchor"]["overridden"] = True
                verification_log["layers"]["origin_anchor"]["passed"] = True
                verification_log["layers"]["origin_anchor"]["reason"] = (
                    f"{l1.get('reason', 'origin failed')}; overridden by approved official source registry"
                )
            else:
                verification_log["verdict"] = "fraud"
                return {
                    "is_verified": False,
                    "verification_log": verification_log,
                    "verdict": "fraud",
                }

        # ---- Layer 2: Cross-Reference ----
        l2 = cross_reference_check(
            event_type, application_url, source_url, metadata
        )
        verification_log["layers"]["cross_reference"] = l2
        # L2 failure is non-fatal — it degrades confidence but doesn't reject

        # ---- Layer 3: Security API Checks ----
        check_url = application_url or source_url
        l3 = security_api_check(check_url)
        verification_log["layers"]["security_api"] = l3

        if not l3["passed"]:
            verification_log["verdict"] = "fraud"
            return {
                "is_verified": False,
                "verification_log": verification_log,
                "verdict": "fraud",
            }

        # All layers passed (or L2 degraded)
        all_l2_passed = l2.get("passed", False)
        if all_l2_passed and l1["passed"] and l3["passed"]:
            verification_log["verdict"] = "verified"
        else:
            verification_log["verdict"] = "degraded"

        return {
            "is_verified": True,  # Not fraud — degraded still passes to scoring
            "verification_log": verification_log,
            "verdict": verification_log["verdict"],
        }


# Module-level singleton
_verifier = Verifier()


def verify_opportunity(
    event_type: str,
    source_url: str = "",
    application_url: str = "",
    source_name: str = "",
    metadata: dict = None,
) -> Dict[str, Any]:
    return _verifier.verify(
        event_type=event_type,
        source_url=source_url,
        application_url=application_url,
        source_name=source_name,
        metadata=metadata,
    )
