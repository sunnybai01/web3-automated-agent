"""Run full source fetch for both schedules and print per-source status summary."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.fetchers.builder import load_sources_config, build_registry


def run_schedule(registry, schedule: str):
    print(f"\n=== RUN {schedule} ===")
    items, status = registry.fetch_all_with_status(schedule)

    ok = [(name, s["items"]) for name, s in status.items() if s["success"]]
    failed = [(name, s.get("error") or "unknown") for name, s in status.items() if not s["success"]]

    print(f"sources_total={len(status)} fetched_items={len(items)}")
    print(f"success={len(ok)} failed={len(failed)}")

    if ok:
        print("\n[SUCCESS]")
        for name, cnt in sorted(ok, key=lambda x: (-x[1], x[0])):
            print(f"- {name}: {cnt} items")

    if failed:
        print("\n[FAILED]")
        for name, err in sorted(failed):
            print(f"- {name}: {err[:200]}")


def main():
    cfg = load_sources_config()
    registry = build_registry(cfg)
    try:
        run_schedule(registry, "grant_hackathon")
        run_schedule(registry, "bounty")
    finally:
        registry.close()


if __name__ == "__main__":
    main()
