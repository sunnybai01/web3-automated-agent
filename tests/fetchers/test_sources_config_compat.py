import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.fetchers.builder import load_sources_config


def test_load_sources_config_preserves_existing_sources_list(tmp_path: Path) -> None:
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


def test_aave_governance_is_disabled_in_repo_config() -> None:
    config = load_sources_config()

    aave_source = next(source for source in config["sources"] if source["name"] == "aave_governance")

    assert aave_source["enabled"] is False


def test_load_sources_config_expands_approved_candidate_chains(tmp_path: Path) -> None:
    sources_path = tmp_path / "sources.yaml"
    candidates_path = tmp_path / "chains.candidates.yaml"

    sources_path.write_text(
        "sources:\n"
        "  - name: base_source\n"
        "    fetch_method: rss\n"
        "    schedule: grant_hackathon\n"
        "    enabled: true\n",
        encoding="utf-8",
    )
    candidates_path.write_text(
        "generated_at: '2026-07-02T00:00:00+00:00'\n"
        "source: defillama\n"
        "candidate_chains:\n"
        "  - chain_id: ethereum\n"
        "    name: Ethereum\n"
        "    review_status: approved\n"
        "    enabled: true\n"
        "  - chain_id: base\n"
        "    name: Base\n"
        "    review_status: pending_review\n"
        "    enabled: true\n"
        "  - chain_id: sui\n"
        "    name: Sui\n"
        "    review_status: approved\n"
        "    enabled: false\n",
        encoding="utf-8",
    )

    config = load_sources_config(str(sources_path), str(candidates_path))

    names = {source["name"] for source in config["sources"]}

    assert "base_source" in names
    assert "defillama_ethereum_grant_hackathon" in names
    assert "defillama_ethereum_bounty" in names
    assert "defillama_base_grant_hackathon" not in names
    assert "defillama_sui_grant_hackathon" not in names

    grant_source = next(
        source
        for source in config["sources"]
        if source["name"] == "defillama_ethereum_grant_hackathon"
    )

    assert grant_source["fetch_method"] == "tavily_search"
    assert grant_source["schedule"] == "grant_hackathon"
    assert grant_source["chain"] == "ethereum"
    assert grant_source["source_tier"] == "discovery"
    assert grant_source["official"] is False


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


def test_phase_one_official_sources_have_expected_metadata() -> None:
    config = load_sources_config()

    arbitrum_grants = next(
        item for item in config["sources"] if item["name"] == "arbitrum_grants"
    )
    avalanche_hackathons = next(
        item
        for item in config["sources"]
        if item["name"] == "avalanche_builder_hackathons"
    )
    avalanche_grants = next(
        item for item in config["sources"] if item["name"] == "avalanche_builder_grants"
    )

    assert arbitrum_grants["fetch_method"] == "web_scraper"
    assert arbitrum_grants["source_tier"] == "official"
    assert arbitrum_grants["official"] is True
    assert arbitrum_grants["schedule"] == "grant_hackathon"
    assert arbitrum_grants["enabled"] is True

    assert avalanche_hackathons["category"] == "hackathon"
    assert avalanche_hackathons["chain"] == "avalanche"
    assert avalanche_hackathons["fetch_method"] == "web_scraper"
    assert avalanche_hackathons["enabled"] is False

    assert avalanche_grants["url"] == "https://build.avax.network/grants/team1-mini-grants"
    assert avalanche_grants["enabled"] is True

    arbitrum_blog = next(
        item
        for item in config["sources"]
        if item["name"] == "arbitrum_foundation_blog"
    )
    base_grants = next(
        item for item in config["sources"] if item["name"] == "base_grants"
    )

    assert arbitrum_blog["enabled"] is True
    assert base_grants["enabled"] is False
    assert base_grants["fetch_method"] == "rss"
    assert base_grants["url"] == "https://paragraph.com/api/blogs/rss/%40grants.base.eth"


def test_repo_sources_include_stellar_scf_rfp_track() -> None:
    config = load_sources_config()

    stellar_rfp = next(
        item for item in config["sources"] if item["name"] == "stellar_scf_rfp_track"
    )

    assert stellar_rfp["fetch_method"] == "web_scraper"
    assert stellar_rfp["schedule"] == "grant_hackathon"
    assert stellar_rfp["category"] == "grant"
    assert stellar_rfp["chain"] == "stellar"
    assert stellar_rfp["source_tier"] == "official"
    assert stellar_rfp["official"] is True
    assert stellar_rfp["enabled"] is True
    assert stellar_rfp["url"] == "https://stellar.gitbook.io/scf-handbook/scf-awards/build-award/rfp-track"


def test_repo_sources_include_social_watch_twitter_sources() -> None:
    config = load_sources_config()
    social_sources = [
        source for source in config["sources"]
        if source.get("schedule") == "social_watch"
    ]

    names = {source["name"] for source in social_sources}

    assert "twitter_gitcoin" in names
    assert "twitter_ethglobal" in names
    assert any(source.get("ingestion_mode") == "preprocessed" for source in social_sources)


def test_repo_sources_include_requested_core_twitter_accounts() -> None:
    config = load_sources_config()
    social_sources = {
        source["name"]: source
        for source in config["sources"]
        if source.get("schedule") == "social_watch"
    }

    expected_screen_names = {
        "twitter_superteamearn": "SuperteamEarn",
        "twitter_bountycaster": "bountycaster",
        "twitter_dorahacks": "DoraHacks",
        "twitter_gitcoin": "gitcoin",
        "twitter_buildonbase": "BuildOnBase",
        "twitter_ef_esp": "EF_ESP",
        "twitter_arbitrum": "Arbitrum",
        "twitter_optimism": "Optimism",
        "twitter_suinetwork": "SuiNetwork",
        "twitter_aptosfoundation": "AptosFoundation",
        "twitter_monad_xyz": "Monad_xyz",
        "twitter_berachain": "berachain",
        "twitter_megalabs_xyz": "MegaLabs_xyz",
    }

    for name, screen_name in expected_screen_names.items():
        assert name in social_sources
        assert social_sources[name]["screen_name"] == screen_name


def test_requested_core_twitter_accounts_are_enabled_for_social_watch_scan() -> None:
    config = load_sources_config()
    social_sources = {
        source["name"]: source
        for source in config["sources"]
        if source.get("schedule") == "social_watch"
    }

    expected_enabled = {
        "twitter_superteamearn",
        "twitter_bountycaster",
        "twitter_dorahacks",
        "twitter_gitcoin",
        "twitter_ethglobal",
        "twitter_buildonbase",
        "twitter_ef_esp",
        "twitter_arbitrum",
        "twitter_optimism",
        "twitter_suinetwork",
        "twitter_aptosfoundation",
        "twitter_monad_xyz",
        "twitter_berachain",
        "twitter_megalabs_xyz",
    }

    for name in expected_enabled:
        assert social_sources[name]["enabled"] is True
