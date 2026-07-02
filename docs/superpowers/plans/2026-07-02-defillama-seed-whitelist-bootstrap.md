# DefiLlama Seed Whitelist Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first working chain-whitelist bootstrap flow by introducing a reviewed chain registry, a DefiLlama seed importer that writes candidate snapshots, and config loading changes that prepare the existing source system for chain-aware evolution.

**Architecture:** Keep the current fetch pipeline behavior intact while adding a parallel configuration layer. The new flow reads DefiLlama chain data, filters and normalizes it into local candidate records, writes a reviewable snapshot file, and adds registry-loading helpers so later fetch orchestration can consume approved chain metadata without refactoring the current runtime yet.

**Tech Stack:** Python 3.11, PyYAML, httpx, pytest

---

### Task 1: Add Chain Registry And Candidate Snapshot Fixtures

**Files:**

- Create: `config/chains.yaml`
- Create: `config/chains.candidates.yaml`
- Create: `tests/fetchers/test_chain_registry_config.py`
- Modify: `src/fetchers/builder.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from src.fetchers.builder import load_chain_registry_config


def test_load_chain_registry_config_reads_registry_file(tmp_path: Path) -> None:
    config_path = tmp_path / "chains.yaml"
    config_path.write_text(
        "chains:\n"
        "  - chain_id: ethereum\n"
        "    name: Ethereum\n"
        "    review_status: approved\n"
        "    enabled: true\n",
        encoding="utf-8",
    )

    config = load_chain_registry_config(str(config_path))

    assert config["chains"][0]["chain_id"] == "ethereum"
    assert config["chains"][0]["review_status"] == "approved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/fetchers/test_chain_registry_config.py -v`
Expected: FAIL with `ImportError` or missing `load_chain_registry_config`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/fetchers/builder.py
from pathlib import Path
import yaml


def load_chain_registry_config(path: str | None = None) -> dict:
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "config" / "chains.yaml"
    with open(path) as f:
        return yaml.safe_load(f)
```

```yaml
# config/chains.yaml
chains:
  - chain_id: ethereum
    name: Ethereum
    defillama_name: Ethereum
    defillama_chain_id: 1
    defillama_slug: ethereum
    seed_tvl: 0
    category: l1
    priority: 1
    review_status: approved
    review_notes: bootstrap seed for official source migration
    enabled: true
```

```yaml
# config/chains.candidates.yaml
generated_at: null
source: defillama
candidate_chains: []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/fetchers/test_chain_registry_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/chains.yaml config/chains.candidates.yaml src/fetchers/builder.py tests/fetchers/test_chain_registry_config.py
git commit -m "feat(config): add chain registry bootstrap"
```

### Task 2: Implement DefiLlama Seed Importer With Review Status Output

**Files:**

- Create: `scripts/sync_defillama_chains.py`
- Create: `tests/scripts/test_sync_defillama_chains.py`
- Modify: `config/settings.py`

- [ ] **Step 1: Write the failing test**

```python
from scripts.sync_defillama_chains import build_candidate_snapshot


def test_build_candidate_snapshot_marks_new_chain_pending_review() -> None:
    api_rows = [
        {
            "name": "Base",
            "tvl": 6631819399.45,
            "chainId": 8453,
            "gecko_id": None,
            "tokenSymbol": None,
        }
    ]
    approved_registry = {
        "chains": [
            {
                "chain_id": "ethereum",
                "name": "Ethereum",
                "defillama_name": "Ethereum",
                "review_status": "approved",
                "enabled": True,
            }
        ]
    }

    snapshot = build_candidate_snapshot(api_rows, approved_registry, top_n=10)

    assert snapshot["candidate_chains"][0]["chain_id"] == "base"
    assert snapshot["candidate_chains"][0]["review_status"] == "pending_review"
    assert snapshot["candidate_chains"][0]["enabled"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_sync_defillama_chains.py -v`
Expected: FAIL because importer module or function is missing.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/sync_defillama_chains.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import sys

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.fetchers.builder import load_chain_registry_config

DEFAULT_URL = "https://api.llama.fi/chains"


def slugify_chain_name(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return value.strip("-")


def build_candidate_snapshot(api_rows: list[dict], registry: dict, top_n: int = 50) -> dict:
    approved_by_name = {
        (item.get("defillama_name") or item.get("name") or "").strip().lower(): item
        for item in registry.get("chains", [])
    }

    ranked = sorted(api_rows, key=lambda row: row.get("tvl") or 0, reverse=True)[:top_n]
    candidates = []

    for row in ranked:
        upstream_name = (row.get("name") or "").strip()
        if not upstream_name:
            continue

        existing = approved_by_name.get(upstream_name.lower())
        candidates.append(
            {
                "chain_id": existing.get("chain_id") if existing else slugify_chain_name(upstream_name),
                "name": existing.get("name") if existing else upstream_name,
                "defillama_name": upstream_name,
                "defillama_chain_id": row.get("chainId"),
                "defillama_slug": row.get("gecko_id"),
                "token_symbol": row.get("tokenSymbol"),
                "seed_tvl": row.get("tvl") or 0,
                "review_status": existing.get("review_status", "pending_review") if existing else "pending_review",
                "enabled": bool(existing.get("enabled", False)) if existing else False,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "defillama",
        "candidate_chains": candidates,
    }


def fetch_defillama_rows(url: str = DEFAULT_URL) -> list[dict]:
    response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    return response.json()


def write_candidate_snapshot(snapshot: dict, output_path: Path) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(snapshot, f, sort_keys=False, allow_unicode=False)
```

```python
# config/settings.py (append)
    DEFILLAMA_CHAINS_URL: str = os.getenv("DEFILLAMA_CHAINS_URL", "https://api.llama.fi/chains")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/scripts/test_sync_defillama_chains.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_defillama_chains.py tests/scripts/test_sync_defillama_chains.py config/settings.py
git commit -m "feat(seed): add defillama chain candidate importer"
```

### Task 3: Add CLI Entry Point And Source Config Compatibility Checks

**Files:**

- Modify: `scripts/sync_defillama_chains.py`
- Create: `tests/fetchers/test_sources_config_compat.py`
- Modify: `src/fetchers/builder.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

```python
from src.fetchers.builder import load_sources_config


def test_load_sources_config_preserves_existing_sources_list(tmp_path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "sources:\n"
        "  - name: ethereum_foundation_esp\n"
        "    fetch_method: rss\n"
        "    enabled: true\n",
        encoding="utf-8",
    )

    config = load_sources_config(str(path))

    assert isinstance(config["sources"], list)
    assert config["sources"][0]["name"] == "ethereum_foundation_esp"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/fetchers/test_sources_config_compat.py -v`
Expected: FAIL only if refactor broke source loading shape.

- [ ] **Step 3: Write minimal implementation**

```python
# src/fetchers/builder.py

def load_sources_config(path: str | None = None) -> dict:
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "config" / "sources.yaml"
    with open(path) as f:
        config = yaml.safe_load(f)
    if "sources" not in config:
        raise ValueError("sources config must contain 'sources'")
    return config
```

```python
# scripts/sync_defillama_chains.py (append)
from argparse import ArgumentParser


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument(
        "--output",
        default=str(ROOT / "config" / "chains.candidates.yaml"),
    )
    args = parser.parse_args()

    registry = load_chain_registry_config()
    rows = fetch_defillama_rows()
    snapshot = build_candidate_snapshot(rows, registry, top_n=args.top_n)
    write_candidate_snapshot(snapshot, Path(args.output))
    print(f"candidate_chains={len(snapshot['candidate_chains'])}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
```

````md
# README.md (append)

## DefiLlama Seed Sync

Generate a reviewed candidate chain snapshot from DefiLlama:

```bash
python scripts/sync_defillama_chains.py --top-n 50
```
````

This command updates `config/chains.candidates.yaml` only. It does not auto-enable chains in `config/chains.yaml`.

````

- [ ] **Step 4: Run tests and the CLI**

Run: `pytest tests/fetchers/test_chain_registry_config.py tests/scripts/test_sync_defillama_chains.py tests/fetchers/test_sources_config_compat.py -v`
Expected: PASS

Run: `python scripts/sync_defillama_chains.py --top-n 10`
Expected: Prints candidate count and output path; `config/chains.candidates.yaml` is updated.

- [ ] **Step 5: Commit**

```bash
git add README.md src/fetchers/builder.py scripts/sync_defillama_chains.py tests/fetchers/test_sources_config_compat.py
git commit -m "docs(seed): add defillama sync workflow"
````
