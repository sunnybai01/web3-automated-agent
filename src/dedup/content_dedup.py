"""L2 semantic deduplication — ChromaDB vector similarity + 15-day sliding window."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session

from config.settings import settings
from src.db.models import Event
from src.db.queries import get_events_in_window, add_event_source, update_event, insert_event
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class ContentDeduplicator:
    """L2 semantic dedup using ChromaDB cosine similarity.

    For each candidate event:
    1. Compute embedding of its text (title + description)
    2. Search ChromaDB for similar events within the 15-day window
    3. If cosine similarity > threshold: it's a duplicate — just add a source link
    4. Otherwise: it's new — index and return
    """

    def __init__(self, vector_store: VectorStore):
        self.vs = vector_store
        self.threshold = settings.SIMILARITY_THRESHOLD  # default: 0.65
        self.window_days = settings.SLIDING_WINDOW_DAYS  # default: 15

    def check_and_process(
        self,
        db: Session,
        event_data: dict,
        source_type: str,
        source_name: str,
        source_url: Optional[str] = None,
        raw_signal_id: Optional[int] = None,
    ) -> Tuple[Optional[int], bool]:
        """
        Returns (event_id, is_new).
        - is_new=True: event was inserted as a new entity.
        - is_new=False: event was identified as a duplicate; its source was appended
          and heat_count incremented. event_id is the existing event's ID.
        """
        title = event_data.get("title", "")
        description = event_data.get("description", "")
        query_text = f"{title} {description}"[:2000]

        # Search ChromaDB for near-duplicates within the window
        similar = self.vs.search_similar(query_text, n_results=5)

        matched_event_id = None
        for doc_id, distance, meta in similar:
            # Cosine distance → similarity: sim = 1 - distance
            similarity = 1.0 - distance
            if similarity >= self.threshold:
                try:
                    matched_event_id = int(doc_id.replace("event_", ""))
                except ValueError:
                    continue

                # Verify the matched event is still within the window
                event = db.query(Event).filter(Event.id == matched_event_id).first()
                if event and event.created_at:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=self.window_days)
                    if event.created_at >= cutoff:
                        logger.info(
                            f"L2 dedup hit: similarity={similarity:.3f} -> event #{matched_event_id}"
                        )
                        break
                matched_event_id = None

        if matched_event_id:
            # Duplicate — append source, increment heat
            add_event_source(
                db,
                event_id=matched_event_id,
                source_type=source_type,
                source_name=source_name,
                source_url=source_url,
                raw_signal_id=raw_signal_id,
            )
            event = db.query(Event).filter(Event.id == matched_event_id).first()
            if event:
                event.heat_count = (event.heat_count or 1) + 1
                db.commit()
            return matched_event_id, False

        # New event — insert, index in ChromaDB
        event = insert_event(db, **event_data)

        # Add initial source record
        add_event_source(
            db,
            event_id=event.id,
            source_type=source_type,
            source_name=source_name,
            source_url=source_url,
            raw_signal_id=raw_signal_id,
        )

        # Index in ChromaDB
        self.vs.add(
            doc_id=f"event_{event.id}",
            text=query_text,
            metadata={
                "event_type": event_data.get("event_type", ""),
                "ecosystem": event_data.get("ecosystem", ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        return event.id, True
