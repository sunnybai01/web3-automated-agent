"""Classification orchestrator — keyword filter → LLM classify → structured extraction."""
import logging
from typing import Optional, Dict, Any, Tuple

from sqlalchemy.orm import Session

from src.fetchers.base import FetchedItem
from .keyword_filter import KeywordFilter
from .llm_gateway import LLMGateway
from .prompts import CLASSIFY_SYSTEM, CLASSIFY_USER_TEMPLATE

logger = logging.getLogger(__name__)


class OpportunityClassifier:
    """Two-stage classifier: keyword coarse filter → LLM fine classification.

    Stage 1 (keyword_filter): fast, cheap, wide recall.
    Stage 2 (llm_gateway): LLM classifies + extracts structured fields.
    """

    CONFIDENCE_THRESHOLD = 0.6

    def __init__(self, keyword_filter: KeywordFilter, llm_gateway: LLMGateway):
        self.keywords = keyword_filter
        self.llm = llm_gateway

    def classify(self, item: FetchedItem) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Classify a single fetched item.

        Returns (category, structured_data).
        - category: "GRANT" | "HACKATHON" | "NOISE" | None (on error)
        - structured_data: full extracted event dict, or None
        """
        # Stage 1: keyword coarse filter
        if not self.keywords.matches(item.raw_content):
            return "NOISE", None

        # Stage 2: LLM fine classification + extraction
        user_prompt = CLASSIFY_USER_TEMPLATE.format(
            title=item.metadata.get("title", "")[:300],
            content=item.raw_content[:3000],
            source_name=item.source_name,
            source_type=item.source_type,
        )

        result = self.llm.classify_structured(CLASSIFY_SYSTEM, user_prompt)
        if not result:
            return None, None

        category = result.get("category", "NOISE")
        confidence = result.get("confidence", 0.0)

        # Bounty opportunities are intentionally out of scope — drop them so no
        # new bounty events are ever created, even if the LLM still emits BOUNTY.
        if category == "BOUNTY":
            return "NOISE", None

        if category == "NOISE" or confidence < self.CONFIDENCE_THRESHOLD:
            return "NOISE", None

        # Merge ecosystem/category hints from source config
        if not result.get("ecosystem"):
            result["ecosystem"] = item.metadata.get("ecosystem")

        return category, result

    def classify_batch(
        self, items: list[FetchedItem]
    ) -> list[Tuple[FetchedItem, Optional[str], Optional[Dict[str, Any]]]]:
        """Classify a batch. Returns list of (item, category, structured_data)."""
        results = []
        for item in items:
            category, data = self.classify(item)
            results.append((item, category, data))
        return results
