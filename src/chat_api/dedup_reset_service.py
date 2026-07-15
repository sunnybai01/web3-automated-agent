"""Service to reset deduplication state for full rescans.

When events are deleted from PostgreSQL but their vectors remain in ChromaDB
and their URLs remain in raw_signals, re-fetching the same sources produces
no new events because both L1 (URL) and L2 (semantic) dedup block them.

This service provides:
- Targeted cleanup: remove vectors + signals for a specific deleted event
- Full reset: clear all ChromaDB vectors and raw_signals for a fresh rescan
"""
import logging

from src.db.database import SessionLocal
from src.db.queries import (
    get_event_signal_ids,
    delete_raw_signals_by_ids,
    purge_orphan_raw_signals,
    truncate_raw_signals,
)
from src.dedup.vector_store import VectorStore

logger = logging.getLogger(__name__)


def cleanup_deleted_event(event_id: int) -> dict:
    """Remove all dedup traces for a single event that was deleted.

    Call AFTER deleting the event from PostgreSQL.
    """
    result = {"event_id": event_id, "signals_deleted": 0, "vector_deleted": False}

    db = SessionLocal()
    try:
        # Delete related raw_signals
        signal_ids = get_event_signal_ids(db, event_id)
        if signal_ids:
            result["signals_deleted"] = delete_raw_signals_by_ids(db, signal_ids)
            logger.info(
                f"Cleaned up {result['signals_deleted']} raw_signals for event #{event_id}"
            )

        # Delete ChromaDB vector
        try:
            vs = VectorStore()
            vs.delete(f"event_{event_id}")
            result["vector_deleted"] = True
            logger.info(f"Cleaned up ChromaDB vector for event #{event_id}")
        except Exception as exc:
            logger.warning(f"Failed to clean ChromaDB vector for event #{event_id}: {exc}")
    finally:
        db.close()

    return result


def reset_all_dedup_state(*, full: bool = False) -> dict:
    """Reset dedup state to allow a clean full rescan.

    Args:
        full: If True, truncate ALL raw_signals. If False, only purge orphans
              (raw_signals not linked to any event).

    Returns:
        Dict with counts of what was cleaned.
    """
    result = {"vectors_cleared": False, "signals_cleared": 0}

    # 1. Clear ChromaDB entirely
    try:
        vs = VectorStore()
        vs.clear_all()
        result["vectors_cleared"] = True
        logger.info("ChromaDB vectors cleared")
    except Exception as exc:
        logger.error(f"Failed to clear ChromaDB: {exc}")
        result["vector_error"] = str(exc)

    # 2. Clean raw_signals
    db = SessionLocal()
    try:
        if full:
            result["signals_cleared"] = truncate_raw_signals(db)
            logger.info(f"Truncated all {result['signals_cleared']} raw_signals")
        else:
            result["signals_cleared"] = purge_orphan_raw_signals(db)
            logger.info(f"Purged {result['signals_cleared']} orphan raw_signals")
    except Exception as exc:
        logger.error(f"Failed to clean raw_signals: {exc}")
        result["signal_error"] = str(exc)
    finally:
        db.close()

    return result
