# Daily Slack Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send one Slack daily summary covering `grant_hackathon`, `bounty`, and `social_watch`, even when no new opportunities were created that day.

**Architecture:** Add a dedicated daily summary scheduler job and a small aggregation service that reads `schedule_log`, `events`, and `event_sources` for the summary day. Use a new `daily_summary_log` table for idempotency so each summary date is sent at most once per channel.

**Tech Stack:** Python, APScheduler, SQLAlchemy, PostgreSQL, Slack SDK, pytest/sqlite-style unit tests.

---

### Task 1: Daily Summary Persistence

**Files:**

- Modify: `src/db/models.py`
- Modify: `src/db/queries.py`
- Test: `tests/db/test_daily_summary_log.py`

- [ ] Add a `DailySummaryLog` model with `summary_date`, `channel`, `status`, `slack_ts`, `error_message`, and a unique constraint on `(summary_date, channel)`.
- [ ] Add query helpers to create a send log row, fetch a row by date/channel, and mark a row success or failure.
- [ ] Write sqlite-backed tests covering create, lookup, and single-row-per-date uniqueness behavior.

### Task 2: Daily Summary Aggregation Service

**Files:**

- Create: `src/dispatch/daily_summary_service.py`
- Modify: `src/db/queries.py`
- Test: `tests/dispatch/test_daily_summary_service.py`

- [ ] Add a summary builder that aggregates same-day `schedule_log` rows for `pipeline_grant_hackathon`, `pipeline_bounty`, and `pipeline_social_watch`.
- [ ] Add support queries for loading same-day `events` and distinct `event_sources.source_name` values tied to those newly created events.
- [ ] Return a structured payload including totals, new events, and distinct new-event source names.
- [ ] Write tests for both “new events exist” and “no new events” cases.

### Task 3: Slack Daily Summary Sender

**Files:**

- Modify: `src/dispatch/slack_client.py`
- Test: `tests/dispatch/test_slack_daily_summary.py`

- [ ] Add `send_daily_summary(summary_payload)` that posts a compact daily summary message to Slack.
- [ ] Format two paths: one with new events and listed source names, one with an explicit no-new-opportunities message.
- [ ] Write tests against a mocked Slack client to verify payload shape and non-configured no-op behavior.

### Task 4: Scheduler and Runtime Wiring

**Files:**

- Modify: `config/settings.py`
- Modify: `src/scheduler/jobs.py`
- Modify: `src/main.py`
- Test: `tests/scheduler/test_jobs.py`
- Test: `tests/config/test_settings.py`

- [ ] Add `DAILY_SUMMARY_ENABLED` and `DAILY_SUMMARY_CRON` settings with safe defaults.
- [ ] Register a new APScheduler cron job when enabled.
- [ ] Add a `run_daily_summary()` entry point in `src/main.py` that builds the summary, enforces idempotency, and sends Slack.
- [ ] Extend scheduler/settings tests to cover the new job and defaults.

### Task 5: End-to-End Idempotent Flow

**Files:**

- Modify: `src/main.py`
- Modify: `src/db/queries.py`
- Test: `tests/test_daily_summary_runtime.py`

- [ ] Ensure a successful send for a given summary date/channel is not repeated.
- [ ] Ensure failures are logged and do not crash unrelated scheduled jobs.
- [ ] Add a focused runtime test that exercises the “already sent today” no-op path.

### Task 6: Docs Update

**Files:**

- Modify: `README.md`

- [ ] Document the new daily summary cron env vars and operator behavior.
- [ ] Mention that the daily summary always posts, even when no new opportunities were found.
