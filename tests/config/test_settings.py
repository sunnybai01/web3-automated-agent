import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from config.settings import Settings


def test_defillama_chains_url_defaults_to_v2_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("DEFILLAMA_CHAINS_URL", raising=False)

    settings = Settings()

    assert settings.DEFILLAMA_CHAINS_URL == "https://api.llama.fi/v2/chains"
