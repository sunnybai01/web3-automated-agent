"""Builds the FetcherRegistry from sources.yaml configuration."""
import logging
import yaml
from pathlib import Path

from .base import FetcherRegistry
from .rss_fetcher import RSSFetcher
from .github_fetcher import GitHubFetcher
from .twitter_fetcher import TwitterFetcher
from .web_scraper import WebScraperFetcher
from .tavily_fetcher import TavilyFetcher

logger = logging.getLogger(__name__)

FETCHER_MAP = {
    "rss": RSSFetcher,
    "github_search": GitHubFetcher,
    "rsshub": TwitterFetcher,
    "web_scraper": WebScraperFetcher,
    "tavily_search": TavilyFetcher,
}


def load_sources_config(path: str = None) -> dict:
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "config" / "sources.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def build_registry(config: dict = None) -> FetcherRegistry:
    """Build and return a FetcherRegistry with all enabled sources."""
    if config is None:
        config = load_sources_config()

    registry = FetcherRegistry()
    sources = config.get("sources", [])

    for src in sources:
        name = src["name"]
        fetch_method = src.get("fetch_method", "rss")
        fetcher_cls = FETCHER_MAP.get(fetch_method)

        if fetcher_cls is None:
            logger.warning(f"No fetcher for method '{fetch_method}' (source '{name}'), skipping")
            continue

        try:
            fetcher = fetcher_cls(source_name=name, config=src,
                                  http_client=registry._http_client)
            registry.register(name, fetcher)
            logger.debug(f"Registered fetcher: {name} ({fetch_method})")
        except Exception as e:
            logger.error(f"Failed to create fetcher for '{name}': {e}")

    logger.info(f"Built registry with {len(registry._fetchers)} fetchers")
    return registry
