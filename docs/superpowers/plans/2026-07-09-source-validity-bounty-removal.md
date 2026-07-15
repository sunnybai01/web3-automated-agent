# Source Validity And Bounty Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop fetching bounty sources and keep only still-valid opportunities with explicit published, start, and deadline times.

**Architecture:** Remove `bounty` from the runtime schedule and source expansion path, then enforce validity in the centralized pipeline staleness gate in `src/main.py`. Extend classifier extraction with `start_date` so the pipeline can reject opportunities without an explicit time window.

**Tech Stack:** Python, pytest, APScheduler, YAML config, LLM structured extraction prompts

## Global Constraints

- Keep changes minimal and localized to existing control points.
- Do not change database schema.
- Preserve historical `bounty` display support.
- Use TDD with narrow pytest validation first.

---

### Task 1: Lock Failing Tests For Bounty Removal And Validity Rules

**Files:**

- Modify: `tests/fetchers/test_sources_config_compat.py`
- Modify: `tests/scheduler/test_jobs.py`
- Modify: `tests/test_main_social_watch.py`

**Interfaces:**

- Consumes: `load_sources_config(path: str | None = None, chain_candidates_path: str | None = None) -> dict`
- Consumes: `register_jobs(scheduler, pipeline_fn, heartbeat_fn, defillama_sync_fn, social_watch_fn, daily_summary_fn)`
- Consumes: `_staleness_reason(item, structured: dict | None, now: datetime | None = None) -> str | None`
- Produces: failing regression coverage for removed bounty runtime paths and stricter validity rules

- [ ] Write failing tests for missing published time, missing start time, missing deadline, and removed bounty runtime paths.
- [ ] Run the targeted pytest selection and confirm the new assertions fail for the current code.

### Task 2: Remove Runtime Bounty Acquisition

**Files:**

- Modify: `config/sources.yaml`
- Modify: `src/fetchers/builder.py`
- Modify: `src/scheduler/jobs.py`
- Modify: `src/chat_api/manual_scan_service.py`
- Modify: `src/main.py`

**Interfaces:**

- Produces: runtime that no longer registers, expands, schedules, or bootstraps `bounty` source fetching

- [ ] Remove static `bounty` source entries from repo config.
- [ ] Stop candidate expansion from creating `defillama_*_bounty` sources.
- [ ] Stop scheduled and startup execution from invoking `run_pipeline("bounty")`.
- [ ] Stop manual scans from invoking `bounty`.

### Task 3: Enforce Explicit Opportunity Time Windows

**Files:**

- Modify: `src/classifier/prompts.py`
- Modify: `src/main.py`

**Interfaces:**

- Produces: classifier output with `start_date`
- Produces: centralized validity gate that rejects items without `published_at`, `start_date`, or `deadline`

- [ ] Add `start_date` to structured extraction prompt and schema.
- [ ] Update `_staleness_reason` to reject missing published timestamps and missing time-window fields before downstream processing.
- [ ] Keep existing stale and expired checks intact.

### Task 4: Validate The Narrow Slice

**Files:**

- Test: `tests/fetchers/test_sources_config_compat.py`
- Test: `tests/scheduler/test_jobs.py`
- Test: `tests/test_main_social_watch.py`

**Interfaces:**

- Produces: passing regression coverage for the changed behavior

- [ ] Run the targeted pytest selection for the touched files.
- [ ] If a failure exposes a local defect in the changed slice, fix it and rerun the same narrow selection.
- [ ] Stop once the targeted slice is green.
