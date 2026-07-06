# Daily Slack Summary Design

## Goal

Add a daily Slack summary that runs at a fixed time and always posts a message for the current day, regardless of whether new opportunities were discovered. The summary must cover all three ingestion schedules: `grant_hackathon`, `bounty`, and `social_watch`.

If new qualified opportunities exist for the day, the summary should include them and list the source names that produced those new events. If no qualified opportunities exist, the summary should still post the day's aggregate pipeline metrics.

## Scope

Included:

- Add a new scheduled job for daily summary posting.
- Aggregate same-day metrics across `grant_hackathon`, `bounty`, and `social_watch`.
- Summarize same-day newly created opportunities.
- Include source names for sources that produced newly created events that day.
- Add Slack formatting for a daily summary message and optional attached report.
- Add idempotency so the daily summary is posted at most once per day for a given summary date.

Excluded:

- Backfilling historical daily summaries.
- Changing the current per-event Slack push behavior.
- Replacing the existing report writer for per-run reports.
- Adding frontend controls for daily summaries.

## Problem Statement

The current pipeline only posts Slack cards when a given run produces `new_events`. This means a day with active ingestion but no newly qualified opportunities produces no Slack visibility at all. Operationally, that makes it hard to distinguish between:

- the pipeline never running,
- the pipeline running but deduping everything,
- the pipeline running and seeing no qualified items,
- Slack delivery failing.

The system needs a fixed-time daily operator-facing summary that answers, for the whole day:

- Did the scheduled jobs run?
- How much content was fetched?
- How much was deduped / classified / verified / pushed?
- Were there any newly created events?
- If yes, which source names produced them?

## Recommended Approach

Create a dedicated `daily_summary` scheduler job rather than overloading the heartbeat job.

Why:

- Daily summary is a reporting concern, not a liveness concern.
- Heartbeat currently runs on a minute interval and is already conceptually overloaded.
- A dedicated cron job is easier to reason about, easier to test, and easier to make idempotent.

The daily summary should be a thin orchestration layer over a dedicated summary service:

1. Query current-day `schedule_log` rows for the three supported schedules.
2. Query newly created `events` for the same day.
3. Join to `event_sources` to determine source names that contributed those new events.
4. Produce a deterministic summary payload.
5. Send the payload to Slack.
6. Record a send log so the same summary date is not sent twice.

## Architecture

### New Scheduler Job

Add a new APScheduler job, for example:

- job id: `daily_slack_summary`
- cron source: `settings.DAILY_SUMMARY_CRON`
- timezone: `Asia/Shanghai`

This job should call a dedicated function from `src.main`, similar to the existing scheduled entry points.

### New Summary Service

Add a small service module responsible for building the daily summary payload. This service should not send Slack itself; it should only compute the summary and produce a structured result.

Responsibilities:

- Determine the summary date window in UTC, aligned to the runtime timezone expectation.
- Aggregate totals across `schedule_log` rows for:
  - `pipeline_grant_hackathon`
  - `pipeline_bounty`
  - `pipeline_social_watch`
- Load `events` created in that date window.
- Join to `event_sources` to identify distinct `source_name` values associated with those newly created events.
- Produce a payload that can be rendered to Slack and, if needed, to a Markdown report.

### New Send Log / Idempotency Record

Add a dedicated persistence mechanism for daily summary sends.

Recommended shape:

- one row per summary date
- summary type/channel marker
- send status
- Slack timestamp if successful
- optional error message

This should be separate from `push_log`, because daily summaries are not event-scoped and should not overload an event-specific audit table.

### Slack Rendering

Add a dedicated Slack method such as `send_daily_summary(summary_payload)`.

The Slack output should always be sent when the job fires and Slack is configured.

Message shape:

- Header with date and summary type
- Aggregate totals for fetched/new/deduped/classified/verified/pushed
- If there are new events:
  - count of new events
  - distinct source names that produced them
  - short list of events with type/title/score/source
- If there are no new events:
  - explicit line: `No new qualified opportunities today`

## Data Model

### Existing Tables Reused

- `schedule_log`: source of daily per-run counters
- `events`: source of newly created opportunities for the day
- `event_sources`: source of `source_name` values tied to newly created events

### New Table

Recommended new table: `daily_summary_log`

Suggested fields:

- `id`
- `summary_date`
- `channel` with default `slack`
- `status` such as `success|failed`
- `slack_ts`
- `created_at`
- `error_message`

Suggested uniqueness:

- unique on `(summary_date, channel)`

This gives exact once-per-day semantics for a given output channel.

## Summary Semantics

### Day Window

Use a fixed daily window corresponding to the operator-facing timezone already used by the scheduler (`Asia/Shanghai`).

That means the summary should cover one logical day in Shanghai time, not simply the last 24 hours.

### What Counts As “New Data” for Listing Sources

Confirmed requirement:

- list source names for sources that produced newly created events that day

This is intentionally narrower than “all fetched sources.” It keeps the report concise and directly tied to outcomes rather than ingestion noise.

### What Counts As “New Event”

Use `events.created_at` within the daily window. The report is about qualified, structured events that actually made it past dedup and into the event store.

## Operational Behavior

### If There Are New Events

Post a daily summary message containing:

- overall counters
- number of new events
- distinct source names responsible for those new events
- a compact event list

### If There Are No New Events

Still post a daily summary containing:

- overall counters
- explicit “no new qualified opportunities” language
- no event list, or an empty-state section

### If Slack Is Not Configured

Do not fail the whole job. Instead:

- log the situation clearly
- optionally still write a local report artifact if that is useful
- mark the daily summary send attempt in a way that makes the failure visible

### If The Job Runs Twice

The second run for the same `summary_date` should not re-send if a successful send record already exists.

## Error Handling

Failure cases to handle explicitly:

- no schedule logs present yet for the day
- no events present for the day
- Slack API failure
- duplicate send attempt for same date
- query failure during aggregation

Expected behavior:

- aggregation failures should mark the summary job failed
- Slack failures should be captured in `daily_summary_log`
- duplicate successful sends should no-op safely

## Testing Strategy

### Unit Tests

- aggregate daily schedule counters correctly across the three schedules
- collect distinct source names from event sources for same-day new events
- produce correct empty-state summary when no new events exist
- enforce daily idempotency

### Integration Tests

- scheduler registration includes the new daily summary job when enabled
- daily summary service produces expected payload from fixture DB rows
- Slack sender formats and attempts delivery using the structured payload

### Regression Checks

- existing event push flow remains unchanged
- no duplicate daily summary post for same day
- daily summary still posts when all runs deduped everything and `new_events == 0`

## File-Level Changes

Primary files to modify:

- `config/settings.py`
  - add `DAILY_SUMMARY_ENABLED`
  - add `DAILY_SUMMARY_CRON`
- `src/scheduler/jobs.py`
  - register new daily summary job
- `src/main.py`
  - add daily summary entry function and wire into scheduler registration
- `src/dispatch/slack_client.py`
  - add daily summary Slack sender
- `src/db/models.py`
  - add `daily_summary_log`
- `src/db/queries.py`
  - add queries for daily summary idempotency and aggregation support

Recommended new files:

- `src/dispatch/daily_summary_service.py`
  - build structured summary payload from DB state

## Open Implementation Decisions Resolved

- Summary scope: all three schedules for the day
- Source listing rule: distinct `source_name` values tied to newly created events that day
- Delivery behavior: always post once per day, even when no new events exist
- Scheduling style: dedicated cron job, not heartbeat piggyback

## Recommendation

Implement this as a narrow additive feature on top of the current pipeline. Do not entangle it with the per-run report logic any more than necessary. The cleanest shape is:

- new scheduler job
- new summary aggregation service
- new Slack daily summary sender
- new summary send log for idempotency

That gives the team guaranteed daily operator visibility without changing the semantics of the existing event-level Slack push flow.
