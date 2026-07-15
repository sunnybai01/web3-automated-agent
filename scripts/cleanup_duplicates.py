#!/usr/bin/env python3
"""
Clean up duplicate events in the database.

Merges sources from duplicate events into the canonical (highest-score) event,
then deletes duplicates. Also updates ChromaDB vector index.

Usage:
    python scripts/cleanup_duplicates.py [--dry-run]
"""

import argparse
import logging
import os
import sys
from pathlib import Path

os.environ["POSTGRES_HOST"] = os.environ.get("EXPERIMENT_PG_HOST", "localhost")
os.environ["CHROMA_HOST"] = os.environ.get("EXPERIMENT_CHROMA_HOST", "localhost")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("cleanup")

from src.db.database import SessionLocal
from src.db.models import Event, EventSource
from src.db.queries import delete_event
from src.dedup.vector_store import VectorStore
from src.dedup.llm_summary import LLMSummaryExtractor


# Canonical event ID → list of duplicate event IDs to merge
# Canonical chosen based on: highest score, most descriptive title
MERGE_PLAN = {
    24: [21, 23, 26],  # Arbitrum Open House cluster
}


def merge_duplicates(db, canonical_id: int, duplicate_ids: list[int], dry_run: bool):
    """Merge sources from duplicates into canonical, then delete duplicates."""
    canonical = db.query(Event).filter(Event.id == canonical_id).first()
    if not canonical:
        logger.error(f"Canonical event #{canonical_id} not found!")
        return

    logger.info(f"Canonical: #{canonical.id} [{canonical.event_type}] {canonical.title[:60]}")

    total_heat = canonical.heat_count or 1
    merged_sources = 0

    for dup_id in duplicate_ids:
        dup = db.query(Event).filter(Event.id == dup_id).first()
        if not dup:
            logger.warning(f"  Duplicate #{dup_id} not found, skipping")
            continue

        # Move EventSource records to canonical
        sources = db.query(EventSource).filter(EventSource.event_id == dup_id).all()
        logger.info(f"  #{dup_id}: {dup.title[:60]} — {len(sources)} source(s) → #{canonical_id}")

        for src in sources:
            if not dry_run:
                src.event_id = canonical_id
                merged_sources += 1

        # Accumulate heat
        total_heat += dup.heat_count or 1

        if not dry_run:
            db.flush()
            # Delete the duplicate event
            db.delete(dup)

    # Update canonical heat_count
    if not dry_run:
        canonical.heat_count = total_heat
        db.commit()
        logger.info(f"  ✅ Merged {merged_sources} sources, heat={total_heat}")
    else:
        logger.info(f"  [DRY RUN] Would merge {merged_sources} sources, heat={total_heat}")


def update_chromadb(db, canonical_id: int, dry_run: bool):
    """Re-index the canonical event in ChromaDB with LLM summary text."""
    try:
        vs = VectorStore()
    except Exception as e:
        logger.warning(f"ChromaDB unavailable, skipping vector store update: {e}")
        return
    extractor = LLMSummaryExtractor()

    canonical = db.query(Event).filter(Event.id == canonical_id).first()
    if not canonical:
        return

    title = canonical.title or ""
    description = canonical.description or ""
    embedding_text = extractor.get_embedding_text(title, description)

    # Remove old ChromaDB entries for duplicates
    for dup_id in MERGE_PLAN.get(canonical_id, []):
        doc_id = f"event_{dup_id}"
        if not dry_run:
            try:
                vs._collection.delete(ids=[doc_id])
                logger.info(f"  ChromaDB: removed event_{dup_id}")
            except Exception as e:
                logger.warning(f"  ChromaDB delete event_{dup_id} failed: {e}")

    # Delete old canonical entry and re-add with new text
    doc_id = f"event_{canonical_id}"
    if not dry_run:
        try:
            vs._collection.delete(ids=[doc_id])
        except Exception:
            pass  # Might not exist yet

        vs.add(
            doc_id=doc_id,
            text=embedding_text,
            metadata={
                "event_type": canonical.event_type or "",
                "ecosystem": canonical.ecosystem or "",
            },
        )
        logger.info(f"  ChromaDB: re-indexed event_{canonical_id} with LLM summary")


def main():
    parser = argparse.ArgumentParser(description="Clean up duplicate events")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no changes")
    args = parser.parse_args()

    if args.dry_run:
        print("🔍 DRY RUN — no changes will be made\n")

    db = SessionLocal()
    try:
        for canonical_id, duplicate_ids in MERGE_PLAN.items():
            print(f"\n{'─' * 60}")
            merge_duplicates(db, canonical_id, duplicate_ids, args.dry_run)
            update_chromadb(db, canonical_id, args.dry_run)

        if not args.dry_run:
            print(f"\n{'=' * 60}")
            print("✅ 清理完成！")

            # Show final state
            print("\n📊 清理后 pushed events:")
            events = (
                db.query(Event)
                .filter(Event.status == "pushed")
                .order_by(Event.id)
                .all()
            )
            for e in events:
                sources = db.query(EventSource).filter(EventSource.event_id == e.id).count()
                print(f"  #{e.id} [{e.event_type}] {e.title[:70]:<70} | heat={e.heat_count} | sources={sources}")
        else:
            print(f"\n{'=' * 60}")
            print("🔍 以上为预览，使用 --no-dry-run 执行实际清理")
    finally:
        db.close()


if __name__ == "__main__":
    main()
