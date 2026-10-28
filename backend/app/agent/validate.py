"""Grounding check for the assistant's final answer.

The model must cite products as [item:ID]. Only IDs that a tool returned in *this* turn are kept;
anything else (a hallucinated ID, or a real ID the model remembered but never looked up) is removed.
"""

import re
from dataclasses import dataclass

CITATION = re.compile(r"\[item:([A-Za-z0-9_-]+)\]")


@dataclass
class ValidatedAnswer:
    text: str  # answer with invalid citations removed
    item_ids: list[str]  # valid cited IDs, in order of first mention
    removed_ids: list[str]  # cited IDs that were not returned by a tool this turn


def validate_answer(text: str, allowed_ids: set[str]) -> ValidatedAnswer:
    """Keep [item:ID] citations whose ID is in `allowed_ids`; strip the rest."""
    kept: list[str] = []
    removed: list[str] = []

    def replace(match: re.Match[str]) -> str:
        item_id = match.group(1)
        if item_id in allowed_ids:
            if item_id not in kept:
                kept.append(item_id)
            return match.group(0)
        if item_id not in removed:
            removed.append(item_id)
        return ""

    cleaned = CITATION.sub(replace, text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return ValidatedAnswer(text=cleaned, item_ids=kept, removed_ids=removed)
