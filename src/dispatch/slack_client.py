"""Slack dispatch — Block Kit cards, Thread silent append, status updates."""
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config.settings import settings
from src.classifier.scorer import stars_from_score

logger = logging.getLogger(__name__)

EMOJI_MAP = {
    "GRANT": "💰",
    "HACKATHON": "🏆",
    "BOUNTY": "🔍",
}

COLOR_MAP = {
    "GRANT": "#2EB67D",     # green
    "HACKATHON": "#E01E5A", # red/pink
    "BOUNTY": "#36C5F0",    # blue
}


def _format_event_type(event_type: str) -> str:
    normalized = (event_type or "other").strip().upper()
    if normalized in {"GRANT", "HACKATHON", "BOUNTY"}:
        return normalized.title()
    return "Other"


class SlackDispatcher:
    """Pushes structured opportunities to Slack via Block Kit."""

    def __init__(self):
        self._configured = bool(settings.SLACK_BOT_TOKEN and settings.SLACK_CHANNEL_ID)
        if self._configured:
            self.client = WebClient(token=settings.SLACK_BOT_TOKEN)
            self.channel_id = settings.SLACK_CHANNEL_ID
        else:
            self.client = None
            self.channel_id = None
            logger.warning("Slack not configured — will generate Markdown reports only")

    @property
    def is_configured(self) -> bool:
        return self._configured

    def push_new_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Push a rich Block Kit card for a new event.

        Returns the Slack message timestamp (slack_ts) on success, None on failure.
        If Slack is not configured, returns None immediately (no-op).
        """
        if not self._configured:
            return None
        event_type_raw = event.get("event_type", "other")
        event_type = (event_type_raw or "other").strip().upper()
        emoji = EMOJI_MAP.get(event_type, "📋")
        color = COLOR_MAP.get(event_type, "#808080")
        type_label = _format_event_type(event_type)
        stars = stars_from_score(event.get("final_score", 5.0))

        title = event.get("title", "Untitled Opportunity")
        amount = event.get("amount") or "Not specified"
        deadline = event.get("deadline") or "Rolling / Not specified"
        if hasattr(deadline, "strftime"):
            deadline = deadline.strftime("%Y-%m-%d")
        ecosystem = event.get("ecosystem", "Unknown").upper()
        track = event.get("track", "General")
        score = event.get("final_score", 0)
        app_url = event.get("application_url", "")
        source_url = event.get("source_url", app_url)
        header_url = source_url or app_url or "https://slack.com"

        # Use a single-column fields block (one field only) to avoid two-column layout.
        detail_text = "\n".join([
            f"*Type:* `{type_label}`",
            f"*Score:* {stars} `{score}/10`",
            f"*Amount:* {amount}",
            f"*Deadline:* {deadline}",
            f"*Ecosystem:* {ecosystem}",
            f"*Track:* {track}",
            f"*Heat:* {event.get('heat_count', 1)} source(s)",
        ])

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{header_url}|{emoji} [{event_type}] {title[:140]}>*",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": detail_text},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": event.get("description", "")[:500] or "No description available.",
                },
            },
            {"type": "divider"},
        ]

        # Action buttons
        actions = {"type": "actions", "elements": []}
        if app_url:
            actions["elements"].append({
                "type": "button",
                "text": {"type": "plain_text", "text": "🚀 Apply Now", "emoji": True},
                "url": app_url,
                "style": "primary",
            })

        if actions["elements"]:
            blocks.append(actions)

        try:
            resp = self.client.chat_postMessage(
                channel=self.channel_id,
                text=f"{emoji} [{event_type}] {title}",  # fallback text
                blocks=blocks,
                unfurl_links=False,
            )
            slack_ts = resp["ts"]
            logger.info(f"Slack push: event #{event.get('id')} -> ts={slack_ts}")
            return slack_ts
        except SlackApiError as e:
            logger.error(f"Slack push failed: {e.response['error']}")
            return None

    def append_to_thread(self, slack_ts: str, event_id: int,
                         source_type: str, source_name: str,
                         source_url: Optional[str] = None) -> bool:
        """Silently append a new source clue to the existing thread."""
        if not self._configured:
            return False
        source_link = f"<{source_url}|{source_name}>" if source_url else source_name
        text = f"🔗 *New source detected:* {source_link} ({source_type})\n_Heat increased for event #{event_id}_"

        try:
            self.client.chat_postMessage(
                channel=self.channel_id,
                thread_ts=slack_ts,
                text=text,
            )
            return True
        except SlackApiError as e:
            logger.error(f"Slack thread append failed: {e.response['error']}")
            return False

    def mark_expired(self, slack_ts: str, original_title: str) -> bool:
        """Update the original card: mark as [EXPIRED] and grey-out."""
        if not self._configured:
            return False
        title = f"🚫 [EXPIRED] {original_title[:120]}"
        try:
            self.client.chat_update(
                channel=self.channel_id,
                ts=slack_ts,
                text=title,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"~{title}~\n\n_This opportunity has expired. The card has been archived._",
                        },
                    },
                ],
            )
            return True
        except SlackApiError as e:
            logger.error(f"Slack update (expire) failed: {e.response['error']}")
            return False

    def send_heartbeat(self, stats: Dict[str, Any]) -> bool:
        """Send a heartbeat message with system stats."""
        if not self._configured:
            return False
        text = (
            f"💓 *Web3 Agent Heartbeat*\n"
            f"Today: {stats.get('fetched', 0)} fetched | "
            f"{stats.get('new', 0)} new | "
            f"{stats.get('deduped', 0)} deduped | "
            f"{stats.get('pushed', 0)} pushed\n"
            f"Unhealthy sources: {stats.get('unhealthy', 0)}"
        )
        try:
            self.client.chat_postMessage(channel=self.channel_id, text=text)
            return True
        except SlackApiError:
            return False

    def send_alert(self, message: str) -> bool:
        """Send an alert to the channel."""
        if not self._configured:
            return False
        try:
            self.client.chat_postMessage(
                channel=self.channel_id,
                text=f"⚠️ *Alert:* {message}",
                icon_emoji=":warning:",
            )
            return True
        except SlackApiError:
            return False

    def upload_report(self, report_path: Path, schedule: str, stats: Dict[str, Any]) -> bool:
        """Upload a generated Markdown report file to Slack as an attachment."""
        if not self._configured:
            return False

        try:
            summary = (
                f"📝 *Run report ({schedule})*\n"
                f"Fetched: {stats.get('fetched', 0)} | "
                f"New: {stats.get('new', 0)} | "
                f"Deduped: {stats.get('deduped', 0)} | "
                f"Verified: {stats.get('verified', 0)} | "
                f"Pushed: {stats.get('pushed', 0)}"
            )

            self.client.files_upload_v2(
                channel=self.channel_id,
                file=str(report_path),
                filename=report_path.name,
                title=f"Web3 Intelligence Report - {schedule}",
                initial_comment=summary,
            )
            logger.info(f"Slack report upload: {report_path}")
            return True
        except SlackApiError as e:
            logger.error(f"Slack report upload failed: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Slack report upload failed: {e}")
            return False
