"""L1 URL deduplication — canonical URL matching + PostgreSQL unique constraint."""
import hashlib
import re
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from sqlalchemy.orm import Session

from src.db.queries import canonical_url_exists, insert_raw_signal
from src.fetchers.base import FetchedItem

# Marketing/tracking params to strip
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content",
    "utm_term", "ref", "referrer", "source", "fbclid", "gclid",
    "gclsrc", "dclid", "twclid", "msclkid", "_ga", "_gl",
}


def normalize_url(url: str) -> str:
    """Strip tracking params, lowercase host, remove trailing slash, resolve known shortlinks."""
    if not url:
        return ""

    parsed = urlparse(url)

    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    netloc = parsed.hostname.lower() if parsed.hostname else ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"

    # Remove fragment
    path = parsed.path.rstrip("/") or "/"

    # Filter tracking params
    qs = parse_qs(parsed.query)
    clean_qs = {k: v for k, v in qs.items() if k not in TRACKING_PARAMS}
    query = urlencode(clean_qs, doseq=True)

    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def generate_content_hash(content: str) -> str:
    """SHA-256 hash of content for dedup indexing."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def process_item_l1(db: Session, item: FetchedItem) -> Optional[int]:
    """L1 dedup: canonical URL check. Returns raw_signal ID if new, None if duplicate.

    Writes to raw_signals table on success. PostgreSQL UNIQUE constraint on
    canonical_url provides the final safety net.
    """
    canonical = normalize_url(item.canonical_url or item.raw_url)
    content_hash = generate_content_hash(item.raw_content)

    # Quick URL dedup check
    if canonical and canonical_url_exists(db, canonical):
        return None

    signal = insert_raw_signal(
        db,
        source_type=item.source_type,
        source_name=item.source_name,
        raw_content=item.raw_content,
        raw_url=item.raw_url,
        canonical_url=canonical,
        content_hash=content_hash,
    )

    return signal.id if signal else None
