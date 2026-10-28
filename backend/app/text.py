"""Cleaning for short user-entered text (board names, display names, notes).

React escapes text when rendering, which is the main XSS defense; this keeps stored values tidy
and strips characters that have no business in a name (control chars, angle brackets).
"""

import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_ANGLE = re.compile(r"[<>]")


def clean_name(value: str, max_length: int = 50) -> str:
    """Normalize, drop control chars and angle brackets, collapse whitespace, and trim. May return ''."""
    text = unicodedata.normalize("NFKC", value)
    text = _ANGLE.sub("", _CONTROL.sub(" ", text))
    return " ".join(text.split())[:max_length].strip()
