"""Layer 3: Third-party security API checks.

Integrates with GoPlus Security, CertiK Skynet, and ScamSniffer
for domain/contract threat intelligence.
"""
import logging
import os
from typing import Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


def check_goplus_domain(domain: str) -> dict:
    """Check a domain against GoPlus Security API.

    Returns {passed, risk_level, detail}.
    """
    api_key = settings.GOPLUS_API_KEY
    if not api_key:
        return {"passed": True, "risk_level": "unknown", "detail": "goplus_not_configured"}

    url = "https://api.gopluslabs.io/api/v1/phishing/site"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params={"url": domain},
                            headers={"Authorization": api_key})
            if resp.status_code != 200:
                return {"passed": True, "risk_level": "unknown", "detail": f"api_error_{resp.status_code}"}
            data = resp.json()
            result = data.get("result", {})
            is_phishing = result.get("phishing_site", False) or result.get("malicious_address", False)

            if is_phishing:
                return {"passed": False, "risk_level": "high",
                        "detail": result.get("phishing_site_detail", "marked_as_phishing")}
            return {"passed": True, "risk_level": "low", "detail": result}
    except Exception as e:
        logger.error(f"GoPlus API error: {e}")
        return {"passed": True, "risk_level": "unknown", "detail": f"api_error:{e}"}


def check_cerik_domain(domain: str) -> dict:
    """Check a domain against CertiK Skynet.

    Returns {passed, risk_level, detail}.
    """
    api_key = settings.CERTIK_API_KEY
    if not api_key:
        return {"passed": True, "risk_level": "unknown", "detail": "certik_not_configured"}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://api.certik.com/v1/skynet/domain",
                params={"domain": domain},
                headers={"X-API-KEY": api_key},
            )
            if resp.status_code != 200:
                return {"passed": True, "risk_level": "unknown", "detail": f"api_error_{resp.status_code}"}
            data = resp.json()
            risk = data.get("risk_level", "unknown")
            if risk in ("critical", "high"):
                return {"passed": False, "risk_level": risk, "detail": data}
            return {"passed": True, "risk_level": risk, "detail": data}
    except Exception as e:
        logger.error(f"CertiK API error: {e}")
        return {"passed": True, "risk_level": "unknown", "detail": f"api_error:{e}"}


def check_scamsniffer(domain: str) -> dict:
    """Check domain age / scam reputation via ScamSniffer.

    Returns {passed, risk_level, detail}.
    """
    api_key = settings.SCAMSNIFFER_API_KEY
    if not api_key:
        return {"passed": True, "risk_level": "unknown", "detail": "scamsniffer_not_configured"}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                "https://api.scamsniffer.io/v1/check",
                json={"url": f"https://{domain}"},
                headers={"X-API-KEY": api_key},
            )
            if resp.status_code != 200:
                return {"passed": True, "risk_level": "unknown", "detail": f"api_error_{resp.status_code}"}
            data = resp.json()
            is_scam = data.get("scam", False)
            days_old = data.get("domain_age_days", None)

            if is_scam:
                return {"passed": False, "risk_level": "high", "detail": "marked_as_scam"}
            if days_old is not None and days_old < 7:
                return {"passed": False, "risk_level": "high",
                        "detail": f"domain_too_new:{days_old}d"}
            return {"passed": True, "risk_level": "low", "detail": data}
    except Exception as e:
        logger.error(f"ScamSniffer API error: {e}")
        return {"passed": True, "risk_level": "unknown", "detail": f"api_error:{e}"}


def security_api_check(url: str) -> dict:
    """Run all security API checks on a URL's domain.

    Returns {passed, checks: [{api_name, passed, risk_level, detail}]}.
    """
    result = {
        "layer": "security_api",
        "passed": True,
        "checks": [],
    }

    if not url:
        result["passed"] = True
        result["reason"] = "no_url_to_check"
        return result

    from urllib.parse import urlparse
    try:
        domain = urlparse(url).hostname
    except Exception:
        result["passed"] = True
        result["reason"] = "invalid_url"
        return result

    if not domain:
        result["passed"] = True
        result["reason"] = "no_hostname"
        return result

    # Run all three checks
    goplus = check_goplus_domain(domain)
    result["checks"].append({"api": "goplus", **goplus})

    certik = check_cerik_domain(domain)
    result["checks"].append({"api": "certik", **certik})

    ss = check_scamsniffer(domain)
    result["checks"].append({"api": "scamsniffer", **ss})

    # Any one check failing = overall fail
    for check in result["checks"]:
        if not check.get("passed", True):
            result["passed"] = False
            result["reason"] = f"{check['api']}:{check.get('detail', 'unknown')}"
            break

    if result["passed"]:
        result["reason"] = "all_security_checks_passed"

    return result
