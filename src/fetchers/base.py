"""Abstract base fetcher — all fetchers inherit from this."""
import datetime as dt
import logging
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

logger = logging.getLogger(__name__)

# Shanghai timezone for Tavily midnight-bound cooldown
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


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


def select_budgeted_sources(
    sources: List[Dict[str, Any]],
    health_by_source: Dict[str, Any],
    schedule: str,
    *,
    fetch_method: str,
    now: Optional[dt.datetime] = None,
) -> set[str]:
    """Select the least-recently-fetched runnable sources under a method budget."""
    now = now or dt.datetime.now(dt.timezone.utc)
    eligible = []
    budgets = []

    for source in sources:
        if source.get("enabled", True) is False:
            continue
        if source.get("schedule") != schedule:
            continue
        if source.get("fetch_method") != fetch_method:
            continue

        budget = int(source.get("max_sources_per_run", 0) or 0)
        if budget > 0:
            budgets.append(budget)

        name = source.get("name")
        health = health_by_source.get(name)
        if get_fetch_skip_reason(source, health, now=now) is not None:
            continue

        last_fetch_at = getattr(health, "last_fetch_at", None) if health is not None else None
        eligible.append((name, last_fetch_at))

    if not eligible:
        return set()

    budget_limit = min(budgets) if budgets else 0
    if budget_limit <= 0 or len(eligible) <= budget_limit:
        return {name for name, _ in eligible}

    eligible.sort(key=lambda row: (row[1] is not None, row[1] or dt.datetime.min.replace(tzinfo=dt.timezone.utc), row[0]))
    return {name for name, _ in eligible[:budget_limit]}


def get_fetch_skip_reason(
    config: Dict[str, Any],
    health: Optional[Any],
    now: Optional[dt.datetime] = None,
    source_state: Optional[Any] = None,
) -> Optional[str]:
    """Return a short skip reason when a source is cooling down.

    Cooldown strategies by fetch method:
    - tavily_search: locked after each successful fetch, auto-unlocks at
      next midnight (Asia/Shanghai).  Rate-limit and failure cooldowns
      still apply as usual.
    - all others: time-based cooldown configured via success_cooldown_minutes,
      rate_limit_cooldown_minutes, and failure_cooldown_minutes.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    fetch_method = config.get("fetch_method", "")

    if source_state is not None and getattr(source_state, "cooldown_until", None) is not None:
        if now < source_state.cooldown_until:
            return "source_state_cooldown"

    if health is None or health.last_fetch_at is None:
        return None

    last_error = (getattr(health, "last_error", "") or "").lower()
    rate_limit_cooldown = int(config.get("rate_limit_cooldown_minutes", 0) or 0)
    failure_cooldown = int(config.get("failure_cooldown_minutes", 0) or 0)

    if "429" in last_error and rate_limit_cooldown > 0:
        retry_at = health.last_fetch_at + dt.timedelta(minutes=rate_limit_cooldown)
        if now < retry_at:
            return "rate_limited_cooldown"

    if getattr(health, "status", None) == "down" and failure_cooldown > 0:
        retry_at = health.last_fetch_at + dt.timedelta(minutes=failure_cooldown)
        if now < retry_at:
            return "failed_source_cooldown"

    # ---- Tavily: midnight-bound cooldown ----
    # A Tavily source that already fetched successfully today is locked
    # until the next midnight (Asia/Shanghai).  The midnight unlock job
    # resets last_success_at → NULL to release all Tavily sources at once.
    if fetch_method == "tavily_search":
        if getattr(health, "last_success_at", None) is not None:
            # Compute the next midnight in Asia/Shanghai (UTC+8)
            shanghai_now = now.astimezone(_SHANGHAI_TZ)
            today_midnight_shanghai = shanghai_now.replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
            if health.last_success_at >= today_midnight_shanghai:
                return "tavily_cooldown_until_midnight"
        return None

    # ---- Standard time-based success cooldown ----
    success_cooldown = int(config.get("success_cooldown_minutes", 0) or 0)
    if success_cooldown > 0 and getattr(health, "last_success_at", None) is not None:
        retry_at = health.last_success_at + dt.timedelta(minutes=success_cooldown)
        if now < retry_at:
            return "success_cooldown"

    return None


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

    def fetch_all_with_status(self, schedule: str, should_skip=None):
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

            skip_reason = should_skip(name, fetcher) if should_skip else None
            if skip_reason:
                source_status[name] = {
                    "success": None,
                    "items": 0,
                    "error": None,
                    "skipped": skip_reason,
                }
                logger.info(f"  {name}: SKIPPED — {skip_reason}")
                continue

            try:
                logger.info(f"Fetching from {name}...")
                items = fetcher.fetch()
                all_items.extend(items)
                source_status[name] = {
                    "success": True,
                    "items": len(items),
                    "error": None,
                    "skipped": None,
                }
                logger.info(f"  {name}: {len(items)} items")
            except Exception as e:
                source_status[name] = {
                    "success": False,
                    "items": 0,
                    "error": str(e),
                    "skipped": None,
                }
                logger.error(f"  {name}: FAILED — {e}")

        return all_items, source_status

    def all_names(self) -> List[str]:
        return list(self._fetchers.keys())

    def close(self):
        self._http_client.close()
        for f in self._fetchers.values():
            f.close()
