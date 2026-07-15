import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    # PostgreSQL
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "web3agent")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "web3agent")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "web3agent")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ChromaDB
    CHROMA_HOST: str = os.getenv("CHROMA_HOST", "localhost")
    CHROMA_PORT: str = os.getenv("CHROMA_PORT", "8000")

    # LLM
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    QWEN_BASE_URL: str = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_BASE_URL: str = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    LLM_PROVIDER_PRIORITY: str = os.getenv("LLM_PROVIDER_PRIORITY", "deepseek,qwen,gemini")

    # Slack
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL_ID: str = os.getenv("SLACK_CHANNEL_ID", "")

    # Security APIs
    GOPLUS_API_KEY: str = os.getenv("GOPLUS_API_KEY", "")
    CERTIK_API_KEY: str = os.getenv("CERTIK_API_KEY", "")
    SCAMSNIFFER_API_KEY: str = os.getenv("SCAMSNIFFER_API_KEY", "")

    # Search / discovery
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    TAVILY_API_KEYS: list[str] = [
        k.strip()
        for k in os.getenv("TAVILY_API_KEYS", os.getenv("TAVILY_API_KEY", "")).split(",")
        if k.strip()
    ]
    TAVILY_SUCCESS_COOLDOWN_MINUTES: int = int(os.getenv("TAVILY_SUCCESS_COOLDOWN_MINUTES", "1440"))
    TAVILY_MAX_SOURCES_PER_RUN: int = int(os.getenv("TAVILY_MAX_SOURCES_PER_RUN", "20"))

    # Twitter (Twikit)
    TWITTER_AUTH_INFO_1: str = os.getenv("TWITTER_AUTH_INFO_1", "")
    TWITTER_AUTH_INFO_2: str = os.getenv("TWITTER_AUTH_INFO_2", "")
    TWITTER_PASSWORD: str = os.getenv("TWITTER_PASSWORD", "")
    TWITTER_TOTP_SECRET: str = os.getenv("TWITTER_TOTP_SECRET", "")
    TWITTER_COOKIES_FILE: str = os.getenv("TWITTER_COOKIES_FILE", ".twitter-cookies.json")
    SOCIAL_WATCH_INTERVAL_MINUTES: int = int(os.getenv("SOCIAL_WATCH_INTERVAL_MINUTES", "240"))
    TWITTER_FETCH_COUNT: int = int(os.getenv("TWITTER_FETCH_COUNT", "20"))

    # App
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    HEARTBEAT_INTERVAL_MINUTES: int = int(os.getenv("HEARTBEAT_INTERVAL_MINUTES", "30"))
    DAILY_SUMMARY_ENABLED: bool = os.getenv("DAILY_SUMMARY_ENABLED", "true").lower() == "true"
    DAILY_SUMMARY_CRON: str = os.getenv("DAILY_SUMMARY_CRON", "55 23 * * *")
    SLIDING_WINDOW_DAYS: int = 14
    SIMILARITY_THRESHOLD: float = 0.75

    # Staleness / time-window enforcement
    # Items published more than this many days ago without ANY deadline are dropped
    # (only applies to discovery sources; official sources are always kept).
    STALE_MAX_AGE_DAYS: int = int(os.getenv("STALE_MAX_AGE_DAYS", "60"))
    # Secondary date extraction timeout when scraping a source URL.
    DATE_SCRAPE_TIMEOUT_SECONDS: int = int(os.getenv("DATE_SCRAPE_TIMEOUT_SECONDS", "15"))
    # Max chars sent to LLM for lightweight date extraction from a scraped page.
    DATE_SCRAPE_MAX_CHARS: int = int(os.getenv("DATE_SCRAPE_MAX_CHARS", "4000"))

    # Scoring weights
    SCORE_WEIGHTS: dict = {
        "roi": 0.40,
        "reputation": 0.30,
        "timeliness": 0.20,
        "strategy": 0.10,
    }


settings = Settings()
