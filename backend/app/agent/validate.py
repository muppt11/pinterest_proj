"""Grounding check for the assistant's final answer.

The model is asked to cite products as [item:ID], but small local models improvise (e.g.
"[Outwear:61d4…]", "[61d4…]", "(item:61d4…)", or a bare ID). Every one of those forms is treated as a
citation: IDs a tool returned in *this* turn are kept (normalized to [item:ID]); anything else is
removed. Lines that were nothing but a citation (a numbered list of IDs) are dropped, because the UI
shows the cited items as picture cards.
"""

import re
from dataclasses import dataclass

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
# [item:ID] / (item: ID) / [Outwear:ID] / [Blazer: ID] / [ID] for any word-ish ID
BRACKETED = re.compile(r"[\[(]\s*(?:([A-Za-z][A-Za-z \-]{0,24}):\s*)?([A-Za-z0-9_-]+)\s*[\])]")
CITATION = re.compile(rf"{BRACKETED.pattern}|\b(?P<bare>{UUID})\b", re.IGNORECASE)
CANONICAL = re.compile(r"\[item:([A-Za-z0-9_-]+)\]")
LIST_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)])?\s*")


@dataclass
class ValidatedAnswer:
    text: str  # answer with invalid citations removed, valid ones as [item:ID]
    item_ids: list[str]  # valid cited IDs, in order of first mention
    removed_ids: list[str]  # cited IDs that were not returned by a tool this turn


def validate_answer(text: str, allowed_ids: set[str]) -> ValidatedAnswer:
    kept: list[str] = []
    removed: list[str] = []

    def cite(item_id: str) -> str:
        if item_id in allowed_ids:
            if item_id not in kept:
                kept.append(item_id)
            return f"[item:{item_id}]"
        if item_id not in removed:
            removed.append(item_id)
        return ""

    def citation(m: re.Match[str]) -> str:
        if m.group("bare"):
            return cite(m.group("bare"))
        label, item_id = m.group(1), m.group(2)
        # A citation is anything explicitly labeled "item:", or a bracket holding a known or UUID-shaped ID.
        if (label or "").strip().lower() == "item" or item_id in allowed_ids or re.fullmatch(UUID, item_id, re.IGNORECASE):
            return cite(item_id)
        return m.group(0)

    # A single pass preserves mention order even when a bare ID precedes a bracketed citation.
    cleaned = CITATION.sub(citation, text)

    # Drop lines that were only a citation (e.g. "1. [item:…]" or a line whose ID was removed).
    lines = []
    for line in cleaned.splitlines():
        rest = CANONICAL.sub("", LIST_PREFIX.sub("", line, count=1)).strip(" ,;:-–")
        if rest or not line.strip():
            lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return ValidatedAnswer(text=cleaned, item_ids=kept, removed_ids=removed)
