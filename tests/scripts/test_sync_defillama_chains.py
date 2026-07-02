import sys
from pathlib import Path

import yaml

sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.sync_defillama_chains import build_candidate_snapshot, sync_candidate_snapshot


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


def test_build_candidate_snapshot_filters_obvious_non_target_chains() -> None:
    api_rows = [
        {"name": "Bitcoin", "tvl": 1000, "chainId": None, "gecko_id": "bitcoin", "tokenSymbol": "BTC"},
        {"name": "Tron", "tvl": 900, "chainId": None, "gecko_id": "tron", "tokenSymbol": "TRX"},
        {"name": "Base", "tvl": 800, "chainId": 8453, "gecko_id": None, "tokenSymbol": None},
        {"name": "Provenance", "tvl": 700, "chainId": None, "gecko_id": "hash-2", "tokenSymbol": "HASH"},
    ]

    snapshot = build_candidate_snapshot(api_rows, {"chains": []}, top_n=10)

    names = [item["defillama_name"] for item in snapshot["candidate_chains"]]
    assert "Base" in names
    assert "Bitcoin" not in names
    assert "Tron" not in names
    assert "Provenance" not in names


def test_sync_candidate_snapshot_writes_output_file(tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "chains.candidates.yaml"

    monkeypatch.setattr(
        "scripts.sync_defillama_chains.load_chain_registry_config",
        lambda: {"chains": []},
    )
    monkeypatch.setattr(
        "scripts.sync_defillama_chains.fetch_defillama_rows",
        lambda url=None: [
            {
                "name": "Base",
                "tvl": 6631819399.45,
                "chainId": 8453,
                "gecko_id": None,
                "tokenSymbol": None,
            }
        ],
    )

    snapshot = sync_candidate_snapshot(output_path=output_path, top_n=50)

    assert output_path.exists()
    written = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert written["candidate_chains"][0]["defillama_name"] == "Base"
    assert snapshot["candidate_chains"][0]["chain_id"] == "base"
