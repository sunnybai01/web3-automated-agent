"""Abstract base fetcher — all fetchers inherit from this."""
import logging
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

logger = logging.getLogger(__name__)


@dataclass
class FetchedItem:
    """Normalized item returned by any fetcher."""
    source_type: str          # rss|github_api|twitter|discord|web_scraper|rsshub
    source_name: str          # config source name
    raw_content: str          # full text/HTML/body
    raw_url: str              # original URL
    canonical_url: str        # normalized URL after redirect resolution
    metadata: Dict[str, Any] = field(default_factory=dict)


class FetchError(Exception):
    """Non-retryable fetch error."""


class BaseFetcher(ABC):
    """Base class for all data source fetchers.

    Subclasses implement ``fetch`` and return a list of FetchedItem.
    The base class handles retry logic, rate limiting, and health reporting.
    """

    source_type: str = "unknown"

    def __init__(self, source_name: str, config: Dict[str, Any],
                 http_client: Optional[httpx.Client] = None):
        self.source_name = source_name
        self.config = config
        self._client = http_client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "Web3-Agent/1.0 (+https://github.com)"},
        )

    @abstractmethod
    def fetch(self) -> List[FetchedItem]:
        """Fetch items from the source. Must be implemented by subclasses."""

    def close(self):
        self._client.close()

    def _canonicalize_url(self, url: str) -> str:
        """Resolve redirects and strip tracking params."""
        if not url:
            return ""
        try:
            resp = self._client.head(url, follow_redirects=True)
            final_url = str(resp.url)
        except Exception:
            final_url = url

        # Strip common marketing/tracking query params
        import re
        final_url = re.sub(r'[?&](utm_source|utm_medium|utm_campaign|utm_content|utm_term|ref|referrer|source)=[^&]*', '', final_url)
        final_url = re.sub(r'\?$', '', final_url)
        return final_url


class FetcherRegistry:
    """Holds all fetcher instances and dispatches by type."""

    def __init__(self):
        self._fetchers: Dict[str, BaseFetcher] = {}
        self._http_client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "Web3-Agent/1.0"},
        )

    def register(self, name: str, fetcher: BaseFetcher):
        self._fetchers[name] = fetcher

    def get(self, name: str) -> Optional[BaseFetcher]:
        return self._fetchers.get(name)

    def fetch_all(self, schedule: str) -> List[FetchedItem]:
        """Fetch from all sources matching a schedule type."""
        all_items, _ = self.fetch_all_with_status(schedule)
        return all_items

    def fetch_all_with_status(self, schedule: str):
        """Fetch from all sources matching a schedule and return per-source status.

        Returns:
            tuple[list[FetchedItem], dict[str, dict]] where status dict contains:
            {"success": bool, "items": int, "error": Optional[str]}
        """
        all_items = []
        source_status = {}

        for name, fetcher in self._fetchers.items():
            if fetcher.config.get("enabled", True) is False:
                continue
            if fetcher.config.get("schedule") != schedule:
                continue

            try:
                logger.info(f"Fetching from {name}...")
                items = fetcher.fetch()
                all_items.extend(items)
                source_status[name] = {
                    "success": True,
                    "items": len(items),
                    "error": None,
                }
                logger.info(f"  {name}: {len(items)} items")
            except Exception as e:
                source_status[name] = {
                    "success": False,
                    "items": 0,
                    "error": str(e),
                }
                logger.error(f"  {name}: FAILED — {e}")

        return all_items, source_status

    def all_names(self) -> List[str]:
        return list(self._fetchers.keys())

    def close(self):
        self._http_client.close()
        for f in self._fetchers.values():
            f.close()
