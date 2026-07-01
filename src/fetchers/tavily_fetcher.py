"""Tavily search fetcher — LLM-optimized web search for opportunity discovery.

Unlike the RSS/scraper fetchers that pull from fixed URLs, this fetcher runs
search queries against the Tavily API to discover grants/hackathons/bounties
that are not covered by any pre-configured feed. Tavily returns pre-extracted,
clean article text, which is ideal for downstream LLM classification.
"""
import hashlib
import logging
from typing import List

from config.settings import settings
from .base import BaseFetcher, FetchedItem, FetchError

logger = logging.getLogger(__name__)

try:
    from tavily import TavilyClient
except ImportError:  # pragma: no cover
    TavilyClient = None


class TavilyFetcher(BaseFetcher):
    """Runs a Tavily search query and normalizes results into FetchedItems.

    Config keys:
        query:        the search query string (required)
        max_results:  number of results to return (default 5)
        search_depth: "basic" | "advanced" (default "advanced")
        topic:        "general" | "news" (default "general")
        days:         when topic == "news", limit to the last N days (default 7)
    """

    source_type = "tavily_search"

    _client_instance = None  # shared TavilyClient across all Tavily fetchers

    def _get_client(self):
        if TavilyClient is None:
            raise FetchError("tavily-python is not installed")
        if not settings.TAVILY_API_KEY:
            raise FetchError("TAVILY_API_KEY not set")
        if TavilyFetcher._client_instance is None:
            TavilyFetcher._client_instance = TavilyClient(api_key=settings.TAVILY_API_KEY)
        return TavilyFetcher._client_instance

    def fetch(self) -> List[FetchedItem]:
        query = self.config.get("query", "")
        if not query:
            raise FetchError(f"Tavily source '{self.source_name}' has no query")

        client = self._get_client()

        max_results = int(self.config.get("max_results", 5))
        search_depth = self.config.get("search_depth", "advanced")
        topic = self.config.get("topic", "general")

        search_kwargs = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "topic": topic,
        }
        if topic == "news":
            search_kwargs["days"] = int(self.config.get("days", 7))

        try:
            response = client.search(**search_kwargs)
        except Exception as e:
            logger.error(f"Tavily search failed for {self.source_name}: {e}")
            raise FetchError(str(e)) from e

        items = []
        for result in response.get("results", []):
            title = result.get("title", "")
            content = result.get("content", "") or ""
            raw_url = result.get("url", "")
            if not raw_url or not content:
                continue

            raw_content = f"{title}\n\n{content}"
            canonical = self._canonicalize_url(raw_url)

            items.append(FetchedItem(
                source_type=self.source_type,
                source_name=self.source_name,
                raw_content=raw_content,
                raw_url=raw_url,
                canonical_url=canonical,
                metadata={
                    "title": title,
                    "platform": "tavily",
                    "content_hash": hashlib.sha256(raw_content.encode()).hexdigest(),
                    "ecosystem": self.config.get("ecosystem"),
                    "category": self.config.get("category"),
                    "tavily_score": result.get("score"),
                    "published_date": result.get("published_date"),
                    "query": query,
                },
            ))

        return items
