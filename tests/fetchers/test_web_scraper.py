import sys
from pathlib import Path

import httpx

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.fetchers.web_scraper import WebScraperFetcher


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, html: str) -> None:
        self._html = html

    def get(self, url: str, timeout: float = 30.0):
        return _FakeResponse(self._html)

    def head(self, url: str, follow_redirects: bool = True):
        return httpx.Response(200, request=httpx.Request("HEAD", url), url=url)

    def close(self) -> None:
        return None


def test_web_scraper_falls_back_to_container_when_matched_cards_are_too_small() -> None:
    html = """
    <html>
      <body>
        <main>
          <div class="card">A</div>
          <div class="card">B</div>
          <section>
            <h1>Official Grant Program</h1>
            <p>
              This Avalanche grant program is open now for builders and provides
              application guidance, eligibility details, and funding support.
            </p>
            <a href="/apply">Apply now</a>
          </section>
        </main>
      </body>
    </html>
    """
    fetcher = WebScraperFetcher(
        "official_grants",
        {
            "name": "official_grants",
            "url": "https://example.com/grants",
            "ecosystem": "avalanche",
            "category": "grant",
        },
        http_client=_FakeClient(html),
    )

    items = fetcher.fetch()

    assert len(items) == 1
    assert items[0].metadata["title"] == "Official Grant Program"
    assert items[0].raw_url == "https://example.com/apply"