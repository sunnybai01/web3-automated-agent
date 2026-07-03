"""Helpers for Twitter social preprocessing and tweet adaptation."""

OPPORTUNITY_TERMS = {
    "grant",
    "grants",
    "hackathon",
    "buildathon",
    "bounty",
    "builder program",
    "rfp",
    "apply",
    "application",
    "deadline",
    "prize",
    "prize pool",
    "security disclosure",
}

OFFICIAL_LINK_HINTS = (
    "foundation",
    ".org/",
    ".org",
    "gitcoin.co",
    "ethglobal.com",
    "immunefi.com",
)


def preprocess_tweet(row: dict, trust_tier: str) -> dict:
    text = " ".join(filter(None, [row.get("text", ""), row.get("quoted_text", "")])).lower()
    has_trigger = any(term in text for term in OPPORTUNITY_TERMS)
    link_urls = row.get("link_urls", []) or []
    has_link = any(url.startswith("https://") for url in link_urls)
    has_official_link = any(hint in url for hint in OFFICIAL_LINK_HINTS for url in link_urls)

    if trust_tier != "discovery":
        return {"verdict": "strong_candidate", "has_official_link": has_official_link}

    if not has_trigger:
        return {"verdict": "drop", "has_official_link": False}
    if has_official_link:
        return {"verdict": "strong_candidate", "has_official_link": True}
    if has_link:
        return {"verdict": "candidate", "has_official_link": False}
    return {"verdict": "drop", "has_official_link": False}


def build_tweet_raw_content(row: dict) -> str:
    lines = [
        f"Author: {row.get('author_screen_name', '')}",
        f"Tweet: {row.get('text', '')}",
    ]
    if row.get("quoted_text"):
        lines.append(f"Quoted tweet: {row['quoted_text']}")
    if row.get("link_urls"):
        lines.append(f"Links: {' '.join(row['link_urls'])}")
    lines.append(f"Source kind: {row.get('source_kind', 'account')}")
    return "\n".join(lines)