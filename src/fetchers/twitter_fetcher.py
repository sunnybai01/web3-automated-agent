"""Twitter/X fetcher via RSSHub bridge."""
import logging
from typing import List
import hashlib

import feedparser
import httpx

from .base import BaseFetcher, FetchedItem, FetchError

logger = logging.getLogger(__name__)


class TwitterFetcher(BaseFetcher):
    """Fetches tweets from specific Twitter accounts via RSSHub bridge.

    Uses RSSHub instances (rsshub.app or self-hosted) which expose
    Twitter timelines as RSS feeds without requiring a Twitter API key.
    """

    source_type = "rsshub"

    def fetch(self) -> List[FetchedItem]:
        url = self.config.get("url", "")
        if not url:
            raise FetchError(f"Twitter source '{self.source_name}' has no RSSHub URL")

        items = []
        try:
            resp = self._client.get(url, timeout=20.0)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"RSSHub fetch failed for {self.source_name}: {e}")
            raise FetchError(str(e)) from e

        feed = feedparser.parse(resp.text)

        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            raw_url = entry.get("link", "")

            # Clean Twitter-specific noise from description
            import re
            clean_summary = re.sub(r'<br\s*/?>', '\n', summary)
            clean_summary = re.sub(r'<[^>]+>', '', clean_summary)
            raw_content = f"{title}\n{clean_summary}"

            canonical = self._canonicalize_url(raw_url)

            items.append(FetchedItem(
                source_type=self.source_type,
                source_name=self.source_name,
                raw_content=raw_content,
                raw_url=raw_url,
                canonical_url=canonical,
                metadata={
                    "title": title,
                    "platform": "twitter",
                    "content_hash": hashlib.sha256(raw_content.encode()).hexdigest(),
                    "ecosystem": self.config.get("ecosystem"),
                    "category": self.config.get("category"),
                },
            ))

        return items
