# Source Validity And Bounty Removal Design

## Goal

Stop fetching bug bounty sources and tighten opportunity validity checks so only still-active opportunities with explicit time windows are kept.

## Scope

- Remove runtime acquisition of `bounty` schedule sources.
- Remove dynamic candidate expansion for `bounty` discovery sources.
- Tighten pipeline-level validity checks for opportunity items.
- Extend structured extraction so classifier output can include a start time.

## Non-Goals

- Removing historical `bounty` records from the database.
- Removing `bounty` from dashboard filters or report rendering for already stored data.
- Refactoring fetcher architecture.

## Design

### Source removal

Use runtime control points instead of per-fetcher logic.

- `config/sources.yaml`: remove or disable static `bounty` sources.
- `src/fetchers/builder.py`: stop generating candidate `bounty` sources.
- `src/scheduler/jobs.py`: stop registering the `bounty` scheduled job.
- `src/chat_api/manual_scan_service.py`: stop manual scans from invoking `bounty`.
- `src/main.py`: stop startup bootstrap from invoking `run_pipeline("bounty")`.

### Validity enforcement

Keep filtering centralized in `src/main.py`.

- A valid opportunity must have a parseable published timestamp.
- A valid opportunity must have a parseable explicit start time.
- A valid opportunity must have a parseable explicit deadline.
- A valid opportunity is stale if the published timestamp is older than the global freshness window.
- A valid opportunity is expired if the deadline is earlier than `now`.

### Extraction update

Update classifier prompts so structured output includes `start_date` as an ISO 8601 string or `null`.
The pipeline will rely on this field when deciding whether an item has an explicit time window.

## Testing

- Add regression tests proving repo config and candidate expansion no longer include `bounty` sources.
- Add regression tests proving scheduler and startup do not invoke `bounty`.
- Add pipeline validity tests for missing published time, missing start time, and missing deadline.
- Run the narrow affected pytest slices first.

## Constraints

- Keep changes minimal and local.
- Do not change storage schema unless required.
- Do not remove `bounty` display support for historical records.
