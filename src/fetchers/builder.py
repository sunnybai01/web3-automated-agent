"""Builds the FetcherRegistry from sources.yaml configuration."""
import logging
import yaml
from pathlib import Path

from config.settings import settings
from .base import FetcherRegistry

logger = logging.getLogger(__name__)


def _repo_config_path(filename: str) -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / filename

FETCHER_MAP = {
    "rss": ".rss_fetcher:RSSFetcher",
    "github_search": ".github_fetcher:GitHubFetcher",
    "rsshub": ".twitter_fetcher:TwitterFetcher",
    "twitter": ".twitter_fetcher:TwitterFetcher",
    "web_scraper": ".web_scraper:WebScraperFetcher",
    "tavily_search": ".tavily_fetcher:TavilyFetcher",
}

DISCOVERY_FETCH_METHODS = {"github_search", "tavily_search"}


def _resolve_fetcher_class(fetch_method: str):
    target = FETCHER_MAP.get(fetch_method)
    if target is None:
        return None

    module_path, class_name = target.split(":", 1)
    module = __import__(f"{__package__}{module_path}", fromlist=[class_name])
    return getattr(module, class_name)


def _normalize_source_metadata(source: dict) -> dict:
    normalized = dict(source)

    fetch_method = normalized.get("fetch_method", "rss")
    ecosystem = normalized.get("ecosystem") or normalized.get("chain") or "multi"
    source_tier = normalized.get("source_tier")

    if source_tier is None:
        source_tier = "discovery" if fetch_method in DISCOVERY_FETCH_METHODS else "official"

    normalized["chain"] = normalized.get("chain") or ecosystem
    normalized["source_tier"] = source_tier
    normalized["official"] = bool(
        normalized.get("official", source_tier == "official")
    )

    is_social_source = fetch_method in {"twitter", "rsshub"} or normalized.get("category") == "social"

    if "signal_type" not in normalized:
        if is_social_source:
            normalized["signal_type"] = "social"
        elif source_tier == "discovery":
            normalized["signal_type"] = "discovery"
        else:
            normalized["signal_type"] = normalized.get("category", "discovery")

    if is_social_source:
        normalized["trust_tier"] = normalized.get("trust_tier") or (
            "discovery" if source_tier == "discovery" else "official"
        )
        normalized["ingestion_mode"] = normalized.get("ingestion_mode") or (
            "preprocessed" if normalized["trust_tier"] == "discovery" else "direct"
        )
        normalized["source_kind"] = normalized.get("source_kind") or "account"
        normalized["watch_priority"] = normalized.get("watch_priority") or "normal"

    if fetch_method == "tavily_search":
        normalized["success_cooldown_minutes"] = int(
            normalized.get("success_cooldown_minutes")
            or settings.TAVILY_SUCCESS_COOLDOWN_MINUTES
        )
        normalized["max_sources_per_run"] = int(
            normalized.get("max_sources_per_run")
            or settings.TAVILY_MAX_SOURCES_PER_RUN
        )

    return normalized


def _load_yaml_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_chain_candidates_config(path: str = None) -> dict:
    if path is None:
        path = _repo_config_path("chains.candidates.yaml")

    candidate_path = Path(path)
    if not candidate_path.exists():
        return {"candidate_chains": []}

    config = _load_yaml_config(candidate_path)
    if "candidate_chains" not in config:
        raise ValueError("chain candidates config must contain 'candidate_chains'")

    return config


def _is_enabled_candidate_chain(chain: dict) -> bool:
    return bool(chain.get("enabled")) and str(chain.get("review_status", "")).lower() == "approved"


def _build_candidate_query(chain_name: str, schedule: str) -> str:
    if schedule == "bounty":
        return (
            f'"{chain_name}" (web3 OR blockchain OR crypto) '
            '(bounty OR bug bounty OR security bounty OR developer bounty)'
        )

    return (
        f'"{chain_name}" (web3 OR blockchain OR crypto) '
        '(grant OR grants OR hackathon OR accelerator OR funding)'
    )


def _build_candidate_sources(chain: dict) -> list[dict]:
    chain_id = chain.get("chain_id")
    chain_name = chain.get("name") or chain.get("defillama_name") or chain_id

    if not chain_id or not chain_name:
        return []

    return [
        {
            "name": f"defillama_{chain_id}_grant_hackathon",
            "type": "tavily_search",
            "fetch_method": "tavily_search",
            "schedule": "grant_hackathon",
            "category": "grant",
            "ecosystem": chain_id,
            "chain": chain_id,
            "source_tier": "discovery",
            "signal_type": "discovery",
            "official": False,
            "enabled": True,
            "max_results": 5,
            "search_depth": "advanced",
            "topic": "news",
            "days": 30,
            "query": _build_candidate_query(chain_name, "grant_hackathon"),
        },
        {
            "name": f"defillama_{chain_id}_bounty",
            "type": "tavily_search",
            "fetch_method": "tavily_search",
            "schedule": "bounty",
            "category": "bounty",
            "ecosystem": chain_id,
            "chain": chain_id,
            "source_tier": "discovery",
            "signal_type": "discovery",
            "official": False,
            "enabled": True,
            "max_results": 5,
            "search_depth": "advanced",
            "topic": "news",
            "days": 30,
            "query": _build_candidate_query(chain_name, "bounty"),
        },
    ]


def _expand_candidate_chain_sources(path: str = None) -> list[dict]:
    config = load_chain_candidates_config(path)
    sources = []

    for chain in config.get("candidate_chains", []):
        if not _is_enabled_candidate_chain(chain):
            continue
        sources.extend(_build_candidate_sources(chain))

    return sources


def load_sources_config(path: str = None, chain_candidates_path: str = None) -> dict:
    if path is None:
        path = _repo_config_path("sources.yaml")
    config = _load_yaml_config(path)

    if "sources" not in config:
        raise ValueError("sources config must contain 'sources'")

    configured_sources = [_normalize_source_metadata(source) for source in config["sources"]]
    candidate_sources = [
        _normalize_source_metadata(source)
        for source in _expand_candidate_chain_sources(chain_candidates_path)
    ]

    config["sources"] = configured_sources + candidate_sources

    return config


def load_chain_registry_config(path: str = None) -> dict:
    if path is None:
        path = _repo_config_path("chains.yaml")
    config = _load_yaml_config(path)

    if "chains" not in config:
        raise ValueError("chain registry config must contain 'chains'")

    return config


def build_registry(config: dict = None) -> FetcherRegistry:
    """Build and return a FetcherRegistry with all enabled sources."""
    if config is None:
        config = load_sources_config()

    registry = FetcherRegistry()
    sources = config.get("sources", [])

    for src in sources:
        name = src["name"]
        if src.get("enabled", True) is False:
            logger.debug(f"Source '{name}' is disabled, skipping registration")
            continue

        fetch_method = src.get("fetch_method", "rss")
        fetcher_cls = _resolve_fetcher_class(fetch_method)

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
