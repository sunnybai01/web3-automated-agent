import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.dispatch import report_writer


def test_generate_report_includes_trust_sections(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_writer, "REPORTS_DIR", tmp_path)

    report_path = report_writer.generate_report(
        events=[
            {
                "event_type": "grant",
                "title": "Base Builder Grants",
                "amount": "$50,000",
                "deadline": "2026-07-30",
                "ecosystem": "base",
                "track": "DeFi",
                "heat_count": 2,
                "description": "Official grants round.",
                "source_url": "https://base.org/grants",
                "application_url": "https://apply.base.org/grants",
                "final_score": 8.2,
                "source_tier": "official",
                "official": True,
                "verification_verdict": "verified",
            },
            {
                "event_type": "hackathon",
                "title": "New Chain Global Hackathon",
                "amount": "$10,000",
                "deadline": "2026-08-15",
                "ecosystem": "newchain",
                "track": "Infra",
                "heat_count": 1,
                "description": "Aggregated from discovery sources.",
                "source_url": "https://ethglobal.com/events/newchain",
                "application_url": "https://ethglobal.com/events/newchain/apply",
                "final_score": 6.1,
                "source_tier": "discovery",
                "official": False,
                "verification_verdict": "degraded",
            },
        ],
        schedule="grant_hackathon",
        stats={"fetched": 2, "new": 2, "deduped": 0, "classified": 2, "verified": 2, "fraud": 0, "pushed": 0},
    )

    content = report_path.read_text(encoding="utf-8")
    assert "Confirmed / Official Signals" in content
    assert "Discovery / Review Needed" in content
    assert "| **Source trust** | Official |" in content
    assert "| **Verification** | Degraded |" in content
