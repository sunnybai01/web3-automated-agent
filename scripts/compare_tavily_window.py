from src.fetchers.builder import load_sources_config
from src.fetchers.tavily_fetcher import TavilyFetcher
from config.settings import settings

config = load_sources_config()
sources = [
    s for s in config.get("sources", [])
    if s.get("enabled", True)
    and s.get("fetch_method") == "tavily_search"
    and s.get("topic", "general") == "news"
][:5]

print("TAVILY_API_KEY configured:", bool(settings.TAVILY_API_KEY))
print("enabled_tavily_news_sources:", len(sources))

for src in sources:
    items7 = TavilyFetcher(source_name=src["name"], config={**src, "days": 7}).fetch()
    items15 = TavilyFetcher(source_name=src["name"], config={**src, "days": 15}).fetch()
    urls7 = {x.raw_url for x in items7}
    extra = [x.raw_url for x in items15 if x.raw_url not in urls7]
    print("SOURCE", src["name"])
    print("days=7", len(items7), "days=15", len(items15), "extra", len(extra))
    for url in extra[:3]:
        print(" +", url)
