from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from argparse import ArgumentParser
import logging
import re
import sys

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import settings
from src.fetchers.builder import load_chain_registry_config


logger = logging.getLogger(__name__)


EXCLUDED_CANDIDATE_NAMES = {
    "binance",
    "bitcoin",
    "plasma",
    "provenance",
    "tron",
}


def slugify_chain_name(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return value.strip("-")


def should_include_chain(row: dict, existing: dict | None) -> bool:
    if existing and existing.get("review_status") == "approved":
        return True

    name = (row.get("name") or "").strip().lower()
    if name in EXCLUDED_CANDIDATE_NAMES:
        return False

    return True


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
        if not should_include_chain(row, existing):
            continue

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


def fetch_defillama_rows(url: str | None = None) -> list[dict]:
    target = url or settings.DEFILLAMA_CHAINS_URL
    response = httpx.get(target, timeout=30.0)
    response.raise_for_status()
    return response.json()


def write_candidate_snapshot(snapshot: dict, output_path: Path) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(snapshot, f, sort_keys=False, allow_unicode=False)


def sync_candidate_snapshot(
    output_path: Path | None = None,
    top_n: int | None = None,
    url: str | None = None,
) -> dict:
    target_path = output_path or (ROOT / "config" / "chains.candidates.yaml")
    effective_top_n = top_n or settings.DEFILLAMA_SYNC_TOP_N

    registry = load_chain_registry_config()
    rows = fetch_defillama_rows(url=url)
    snapshot = build_candidate_snapshot(rows, registry, top_n=effective_top_n)
    write_candidate_snapshot(snapshot, target_path)
    logger.info(
        "DefiLlama candidate snapshot updated: %s chains -> %s",
        len(snapshot["candidate_chains"]),
        target_path,
    )
    return snapshot


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument(
        "--output",
        default=str(ROOT / "config" / "chains.candidates.yaml"),
    )
    args = parser.parse_args()

    snapshot = sync_candidate_snapshot(output_path=Path(args.output), top_n=args.top_n)

    print(f"candidate_chains={len(snapshot['candidate_chains'])}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
