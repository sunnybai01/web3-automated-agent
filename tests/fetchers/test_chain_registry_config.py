import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

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


def test_stellar_is_approved_in_repo_chain_registry() -> None:
    config = load_chain_registry_config()

    stellar = next(chain for chain in config["chains"] if chain["chain_id"] == "stellar")

    assert stellar["review_status"] == "approved"
    assert stellar["enabled"] is True


def test_followup_chains_are_approved_in_repo_chain_registry() -> None:
    config = load_chain_registry_config()
    expected_chain_ids = {
        "aptos",
        "starknet",
        "near",
        "arbitrum",
        "base",
        "polygon",
        "avalanche",
        "monad",
    }

    approved = {
        chain["chain_id"]
        for chain in config["chains"]
        if chain.get("review_status") == "approved" and chain.get("enabled") is True
    }

    assert expected_chain_ids.issubset(approved)
