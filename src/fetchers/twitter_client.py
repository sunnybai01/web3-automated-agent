"""Twitter timeline client helpers with a direct guest GraphQL fallback."""
import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


class TwikitTimelineClient:
    """Small wrapper around Twikit to keep fetcher code sync-friendly."""

    def __init__(self, settings):
        self._settings = settings

    async def _build_logged_in_client(self):
        from twikit import Client

        client = Client(language="en-US")
        await client.login(
            auth_info_1=self._settings.TWITTER_AUTH_INFO_1,
            auth_info_2=self._settings.TWITTER_AUTH_INFO_2 or None,
            password=self._settings.TWITTER_PASSWORD,
            totp_secret=self._settings.TWITTER_TOTP_SECRET or None,
            cookies_file=self._settings.TWITTER_COOKIES_FILE,
        )
        return client

    @staticmethod
    def _guest_headers() -> dict[str, str]:
        from twikit.constants import TOKEN

        return {
            "authorization": f"Bearer {TOKEN}",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
            ),
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "en",
        }

    @staticmethod
    def _json_param(value: dict) -> str:
        return json.dumps(value, separators=(",", ":"))

    @staticmethod
    def _extract_user_rest_id(payload: dict) -> str:
        return payload["data"]["user"]["result"]["rest_id"]

    @staticmethod
    def _unwrap_tweet_result(result: dict | None) -> dict | None:
        if not result:
            return None

        if result.get("__typename") == "TweetWithVisibilityResults":
            result = result.get("tweet")

        if isinstance(result, dict) and "result" in result and "rest_id" not in result:
            result = result.get("result")

        if not isinstance(result, dict) or "rest_id" not in result:
            return None

        return result

    @staticmethod
    def _tweet_text(result: dict) -> str:
        note_results = (
            result.get("note_tweet", {})
            .get("note_tweet_results", {})
            .get("result", {})
        )
        if note_results.get("text"):
            return note_results["text"]
        return result.get("legacy", {}).get("full_text", "") or ""

    @staticmethod
    def _tweet_urls(result: dict) -> list[str]:
        note_results = (
            result.get("note_tweet", {})
            .get("note_tweet_results", {})
            .get("result", {})
        )
        entities = note_results.get("entity_set") or result.get("legacy", {}).get("entities", {})
        urls = []
        for url in entities.get("urls", []) or []:
            expanded = url.get("expanded_url") or url.get("url")
            if expanded:
                urls.append(expanded)
        return urls

    @classmethod
    def _quoted_tweet_text(cls, result: dict) -> str:
        quoted_result = result.get("quoted_status_result", {})
        quoted = cls._unwrap_tweet_result(quoted_result)
        if quoted:
            return cls._tweet_text(quoted)
        return quoted_result.get("result", {}).get("legacy", {}).get("full_text", "") or ""

    @staticmethod
    def _parse_twitter_created_at(value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            for fmt in ("%a %b %d %H:%M:%S %z %Y",):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return None

    @classmethod
    def _normalize_tweet_result(cls, result: dict, default_screen_name: str) -> dict:
        author = (
            result.get("core", {})
            .get("user_results", {})
            .get("result", {})
            .get("legacy", {})
            .get("screen_name")
        ) or default_screen_name

        return {
            "id": str(result.get("rest_id", "")),
            "url": f"https://x.com/{author}/status/{result.get('rest_id', '')}",
            "text": cls._tweet_text(result),
            "author_screen_name": author,
            "quoted_text": cls._quoted_tweet_text(result),
            "link_urls": cls._tweet_urls(result),
            "created_at": cls._parse_twitter_created_at(result.get("legacy", {}).get("created_at")),
        }

    @classmethod
    def _extract_timeline_rows(
        cls,
        payload: dict,
        default_screen_name: str,
        max_count: int | None = None,
    ) -> tuple[list[dict], str | None]:
        instructions = (
            payload.get("data", {})
            .get("user", {})
            .get("result", {})
            .get("timeline_v2", {})
            .get("timeline", {})
            .get("instructions", [])
        )

        rows = []
        next_cursor = None
        reached_limit = False

        for instruction in instructions:
            entries = []
            if instruction.get("type") == "TimelineAddEntries":
                entries = instruction.get("entries", [])
            elif instruction.get("type") == "TimelinePinEntry" and instruction.get("entry"):
                entries = [instruction["entry"]]

            for entry in entries:
                content = entry.get("content", {})
                if content.get("cursorType") == "Bottom" and content.get("value"):
                    next_cursor = content.get("value")

                if not str(entry.get("entryId", "")).startswith("tweet-"):
                    continue

                if reached_limit:
                    continue

                result = cls._unwrap_tweet_result(
                    content.get("itemContent", {})
                    .get("tweet_results", {})
                    .get("result")
                )
                if result is None:
                    continue
                rows.append(cls._normalize_tweet_result(result, default_screen_name))
                if max_count is not None and len(rows) >= max_count:
                    reached_limit = True

        return rows, next_cursor

    async def _activate_guest_token(self, client: httpx.AsyncClient, headers: dict[str, str]) -> str:
        response = await client.post(
            "https://api.x.com/1.1/guest/activate.json",
            headers=headers,
            json={},
        )
        response.raise_for_status()
        return response.json()["guest_token"]

    async def _guest_gql_get(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        variables: dict,
        features: dict,
        extra_params: dict | None = None,
    ) -> dict:
        headers = self._guest_headers()
        guest_token = await self._activate_guest_token(client, headers)
        params = {
            "variables": self._json_param(variables),
            "features": self._json_param(features),
        }
        if extra_params:
            params.update({key: self._json_param(value) for key, value in extra_params.items()})

        response = await client.get(
            url,
            headers={**headers, "x-guest-token": guest_token},
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def _fetch_account_tweets_via_guest(
        self,
        *,
        screen_name: str,
        count: int,
        cursor: str | None,
    ):
        from twikit.client.gql import Endpoint, FEATURES, USER_FEATURES

        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            user_payload = await self._guest_gql_get(
                client,
                Endpoint.USER_BY_SCREEN_NAME,
                variables={
                    "screen_name": screen_name,
                    "withSafetyModeUserFields": False,
                },
                features=USER_FEATURES,
                extra_params={"fieldToggles": {"withAuxiliaryUserLabels": False}},
            )
            user_id = self._extract_user_rest_id(user_payload)
            timeline_variables = {
                "userId": user_id,
                "count": count,
                "includePromotedContent": True,
                "withQuickPromoteEligibilityTweetFields": True,
                "withVoice": True,
                "withV2Timeline": True,
            }
            if cursor is not None:
                timeline_variables["cursor"] = cursor

            timeline_payload = await self._guest_gql_get(
                client,
                Endpoint.USER_TWEETS,
                variables=timeline_variables,
                features=FEATURES,
            )
            return self._extract_timeline_rows(
                timeline_payload,
                screen_name,
                max_count=count,
            )

    def fetch_account_tweets(self, *, screen_name: str, count: int, cursor: str | None):
        return asyncio.run(
            self._fetch_account_tweets(screen_name=screen_name, count=count, cursor=cursor)
        )

    async def _fetch_account_tweets(self, *, screen_name: str, count: int, cursor: str | None):
        try:
            return await self._fetch_account_tweets_via_guest(
                screen_name=screen_name,
                count=count,
                cursor=cursor,
            )
        except Exception as exc:
            logger.warning("Guest Twitter fetch failed for %s: %s", screen_name, exc)

        client = await self._build_logged_in_client()
        user = await client.get_user_by_screen_name(screen_name)
        tweets = await client.get_user_tweets(user.id, "Tweets", count=count, cursor=cursor)
        rows = [self._normalize_tweet(tweet, screen_name) for tweet in tweets]
        return rows, getattr(tweets, "next_cursor", None)

    def fetch_list_tweets(self, *, list_id: str, count: int, cursor: str | None):
        return asyncio.run(self._fetch_list_tweets(list_id=list_id, count=count, cursor=cursor))

    async def _fetch_list_tweets(self, *, list_id: str, count: int, cursor: str | None):
        client = await self._build_logged_in_client()
        tweets = await client.get_list_tweets(list_id, count=count, cursor=cursor)
        rows = [self._normalize_tweet(tweet, getattr(getattr(tweet, "user", None), "screen_name", "")) for tweet in tweets]
        return rows, getattr(tweets, "next_cursor", None)

    @staticmethod
    def _normalize_tweet(tweet, default_screen_name: str) -> dict:
        urls = []
        for url in getattr(tweet, "urls", []) or []:
            expanded = None
            if isinstance(url, dict):
                expanded = url.get("expanded_url") or url.get("url")
            else:
                expanded = getattr(url, "expanded_url", None) or getattr(url, "url", None)
            if expanded:
                urls.append(expanded)

        author = getattr(getattr(tweet, "user", None), "screen_name", None) or default_screen_name
        quote = getattr(tweet, "quote", None)

        return {
            "id": str(getattr(tweet, "id", "")),
            "url": getattr(tweet, "url", None) or f"https://x.com/{author}/status/{getattr(tweet, 'id', '')}",
            "text": getattr(tweet, "text", "") or "",
            "author_screen_name": author,
            "quoted_text": getattr(quote, "text", "") or "",
            "link_urls": urls,
            "created_at": TwikitTimelineClient._parse_twitter_created_at(getattr(tweet, "created_at", None)),
        }