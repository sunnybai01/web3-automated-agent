"""HTML web scraper — fallback for sites without RSS/API."""
import logging
from typing import List
import hashlib

import httpx
from bs4 import BeautifulSoup

from .base import BaseFetcher, FetchedItem, FetchError

logger = logging.getLogger(__name__)


class WebScraperFetcher(BaseFetcher):
    """Scrapes web pages directly for grant/hackathon/bounty information.

    Used only when no RSS or API is available. Extracts text content
    from <article>, <main>, or <body> tags and splits into blocks.
    """

    source_type = "web_scraper"

    def fetch(self) -> List[FetchedItem]:
        url = self.config.get("url", "")
        if not url:
            raise FetchError(f"Web scraper '{self.source_name}' has no URL")

        try:
            resp = self._client.get(url, timeout=30.0)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Web scrape failed for {self.source_name}: {e}")
            raise FetchError(str(e)) from e

        soup = BeautifulSoup(resp.text, "lxml")

        # Prefer semantic containers
        container = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_="content")
            or soup.body
        )
        if not container:
            return []

        # Remove scripting and styling
        for tag in container.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        items = []
        # Strategy: look for individual entries (list items, cards, articles)
        entries = (
            container.find_all("article")
            or container.find_all(["li", "div"], class_=lambda c: c and any(
                kw in (c or "") for kw in ["item", "card", "entry", "post", "result", "row"]
            ))
            or [container]  # fallback: treat entire page as one block
        )

        for entry in entries:
            text = entry.get_text(separator="\n", strip=True)
            if not text or len(text) < 50:
                continue

            # Try to find a link in this entry
            link_tag = entry.find("a", href=True)
            raw_url = link_tag["href"] if link_tag else url
            if raw_url.startswith("/"):
                from urllib.parse import urljoin
                raw_url = urljoin(url, raw_url)

            canonical = self._canonicalize_url(raw_url)

            items.append(FetchedItem(
                source_type=self.source_type,
                source_name=self.source_name,
                raw_content=text,
                raw_url=raw_url,
                canonical_url=canonical,
                metadata={
                    "title": text.split("\n")[0][:200] if text else "",
                    "content_hash": hashlib.sha256(text.encode()).hexdigest(),
                    "ecosystem": self.config.get("ecosystem"),
                    "category": self.config.get("category"),
                },
            ))

            if len(items) >= 20:
                break

        return items
