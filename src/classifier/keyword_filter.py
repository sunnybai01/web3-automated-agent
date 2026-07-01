"""Coarse keyword filter — wide recall, passes candidates to LLM for fine classification."""
import re
import logging
from typing import List, Optional
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class KeywordFilter:
    """Fast text-based filter: checks content against keyword lists.

    Designed for HIGH RECALL (better to pass noise to the LLM than miss a signal).
    """

    def __init__(self, keywords_path: str = None):
        if keywords_path is None:
            keywords_path = Path(__file__).resolve().parent.parent.parent / "config" / "keywords.yaml"
        with open(keywords_path) as f:
            config = yaml.safe_load(f)

        self.keywords = config.get("keywords", {})
        self.flags = config.get("flags", {})
        self.case_sensitive = self.flags.get("case_sensitive", False)
        self.min_hits = self.flags.get("min_keyword_hits", 2)

        # Compile regex patterns for efficiency
        self._compile_patterns()

    def _compile_patterns(self):
        self._patterns = {}
        for category, words in self.keywords.items():
            if category == "negative":
                continue
            escaped = [re.escape(w) for w in words]
            flags = 0 if self.case_sensitive else re.IGNORECASE
            self._patterns[category] = re.compile(
                "|".join(escaped), flags=flags
            )

        # Negative keywords are compiled separately
        neg_words = self.keywords.get("negative", [])
        flags = 0 if self.case_sensitive else re.IGNORECASE
        self._negative_pattern = re.compile(
            "|".join(re.escape(w) for w in neg_words), flags=flags
        ) if neg_words else None

    def matches(self, text: str) -> bool:
        """Return True if text should pass to LLM classification."""
        if not text:
            return False

        # Immediate reject on negative keywords
        if self._negative_pattern and self._negative_pattern.search(text):
            logger.debug("Rejected by negative keyword match")
            return False

        # Count keyword hits across all categories
        total_hits = 0
        for category, pattern in self._patterns.items():
            hits = len(pattern.findall(text))
            total_hits += hits

        passed = total_hits >= self.min_hits
        if not passed:
            logger.debug(f"Keyword filter: {total_hits} hits < {self.min_hits} threshold")
        return passed

    def get_matched_categories(self, text: str) -> List[str]:
        """Return which categories were matched (for routing hints)."""
        matched = []
        for category, pattern in self._patterns.items():
            if pattern.search(text):
                matched.append(category)
        return matched
