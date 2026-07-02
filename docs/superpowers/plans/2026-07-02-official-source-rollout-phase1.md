# Phase-One Official Source Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first validated official recurring sources for Base, Arbitrum, Polygon, and Avalanche to the source registry, then verify which ones should remain enabled.

**Architecture:** Keep the change entirely in configuration and tests. Add the smallest set of official recurring sources to `config/sources.yaml`, verify they load through the existing source builder, then run focused live fetch validation before deciding their enabled state.

**Tech Stack:** YAML config, pytest, existing RSS fetcher, existing web scraper fetcher, Docker Compose runtime

---

### Task 1: Lock The First-Phase Official Source Set

**Files:**

- Modify: `tests/fetchers/test_sources_config_compat.py`
- Modify: `config/sources.yaml`

- [ ] **Step 1: Write the failing test**

```python
def test_phase_one_official_sources_exist_in_repo_config() -> None:
    config = load_sources_config()
    names = {source["name"] for source in config["sources"]}

    expected = {
        "base_blog",
        "base_grants",
        "arbitrum_grants",
        "arbitrum_foundation_blog",
        "polygon_blog",
        "avalanche_builder_grants",
        "avalanche_builder_hackathons",
        "avalanche_blog",
    }

    assert expected.issubset(names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/fetchers/test_sources_config_compat.py -q`
Expected: FAIL because the new official source names are missing from repo config.

- [ ] **Step 3: Write minimal implementation**

Add these entries to `config/sources.yaml` with chain-aware metadata and `enabled: false`:

```yaml
- name: base_blog
  type: rss
  url: https://blog.base.dev/rss
  schedule: grant_hackathon
  category: grant
  ecosystem: base
  chain: base
  fetch_method: rss
  source_tier: official
  signal_type: grant
  official: true
  enabled: false
```

Repeat the same pattern for:

- `base_grants`
- `arbitrum_grants`
- `arbitrum_foundation_blog`
- `polygon_blog`
- `avalanche_builder_grants`
- `avalanche_builder_hackathons`
- `avalanche_blog`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/fetchers/test_sources_config_compat.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/fetchers/test_sources_config_compat.py config/sources.yaml
git commit -m "feat: add phase-one official source candidates"
```

### Task 2: Validate Source Metadata Shape

**Files:**

- Modify: `tests/fetchers/test_sources_config_compat.py`
- Modify: `config/sources.yaml`

- [ ] **Step 1: Write the failing test**

```python
def test_phase_one_official_sources_have_expected_metadata() -> None:
    config = load_sources_config()
    source = next(item for item in config["sources"] if item["name"] == "arbitrum_grants")

    assert source["fetch_method"] == "web_scraper"
    assert source["source_tier"] == "official"
    assert source["official"] is True
    assert source["schedule"] == "grant_hackathon"
```

````

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/fetchers/test_sources_config_compat.py -q`
Expected: FAIL if any metadata field is wrong or missing.

- [ ] **Step 3: Write minimal implementation**

Use these fetcher assignments:

- `base_blog`: `rss`
- `base_grants`: `web_scraper`
- `arbitrum_grants`: `web_scraper`
- `arbitrum_foundation_blog`: `web_scraper`
- `polygon_blog`: `web_scraper`
- `avalanche_builder_grants`: `web_scraper`
- `avalanche_builder_hackathons`: `web_scraper`
- `avalanche_blog`: `web_scraper`

Apply consistent metadata:

```yaml
source_tier: official
official: true
schedule: grant_hackathon
````

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/fetchers/test_sources_config_compat.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/fetchers/test_sources_config_compat.py config/sources.yaml
git commit -m "test: lock official source metadata"
```

### Task 3: Run Focused Runtime Validation

**Files:**

- Modify: `config/sources.yaml`

- [ ] **Step 1: Rebuild runtime containers**

Run: `docker compose up -d --build agent-app chat-api`
Expected: containers restart successfully.

- [ ] **Step 2: Run live fetch validation against the new sources**

Run:

```bash
docker exec web3_agent_main python - <<'PY'
from src.fetchers.builder import load_sources_config, build_registry

target_names = {
    "base_blog",
    "base_grants",
    "arbitrum_grants",
    "arbitrum_foundation_blog",
    "polygon_blog",
    "avalanche_builder_grants",
    "avalanche_builder_hackathons",
    "avalanche_blog",
}

config = load_sources_config()
for source in config["sources"]:
    if source["name"] in target_names:
        source["enabled"] = True

registry = build_registry(config)
for name in target_names:
    fetcher = registry.get(name)
    items = fetcher.fetch()
    print(name, len(items))
registry.close()
PY
```

Expected: a per-source item count and any failures clearly surfaced.

- [ ] **Step 3: Keep only stable sources enabled**

If a source returns meaningful items without access errors, update that source to:

```yaml
enabled: true
```

If it fails, leave:

```yaml
enabled: false
```

- [ ] **Step 4: Rebuild runtime again**

Run: `docker compose up -d --build agent-app chat-api`
Expected: runtime now reflects the final enabled state.

- [ ] **Step 5: Commit**

```bash
git add config/sources.yaml
git commit -m "feat: enable validated official opportunity sources"
```
