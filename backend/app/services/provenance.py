"""Evidence-based AI labels from provenance metadata. Never guessed from pixels.

Three labels:
- "ai_generated": a valid C2PA manifest, or an IPTC DigitalSourceType tag, declares an AI source.
- "human_verified": a *valid C2PA signature* declares a camera capture (digitalCapture). Unsigned
  IPTC claims of a camera capture are easy to fake, so they don't earn "verified".
- "unknown": no usable provenance (the default), or a C2PA manifest that failed validation.

Must run on the original upload bytes, before any re-encoding or metadata stripping.
"""

import io
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Literal

Label = Literal["ai_generated", "human_verified", "unknown"]

IPTC_BASE = "http://cv.iptc.org/newscodes/digitalsourcetype/"
AI_SOURCE_TYPES = {
    "trainedAlgorithmicMedia",
    "compositeWithTrainedAlgorithmicMedia",
    "algorithmicMedia",
    "compositeSynthetic",
}
CAPTURE_SOURCE_TYPES = {"digitalCapture"}

_IPTC_PATTERN = re.compile(rb"DigitalSourceType\s*(?:=\s*[\"']|>)\s*(?:" + re.escape(IPTC_BASE.encode()) + rb")?([A-Za-z]+)")


@dataclass
class Evidence:
    source: str  # "C2PA" or "IPTC"
    field: str  # where it was found
    value: str
    note: str = ""


@dataclass
class Provenance:
    label: Label
    explanation: str
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"label": self.label, "explanation": self.explanation, "evidence": [asdict(e) for e in self.evidence]}


def _source_type(value: str) -> str:
    return value.rsplit("/", 1)[-1]


def read_c2pa(data: bytes, mime: str) -> tuple[list[str], str | None, str | None]:
    """(digitalSourceType codes from the active manifest's actions, validation state, signer/issuer).
    Returns ([], None, None) when there is no manifest."""
    try:
        import c2pa
    except ImportError:  # library not installed: treat as no evidence
        return [], None, None
    try:
        reader = c2pa.Reader(mime, io.BytesIO(data))
    except Exception:  # no manifest (the common case) or unreadable
        return [], None, None
    try:
        store = json.loads(reader.json())
        state = reader.get_validation_state() if hasattr(reader, "get_validation_state") else None
        active = store.get("manifests", {}).get(store.get("active_manifest") or "", {})
        codes = []
        for assertion in active.get("assertions", []):
            if assertion.get("label", "").startswith("c2pa.actions"):
                for action in assertion.get("data", {}).get("actions", []):
                    if action.get("digitalSourceType"):
                        codes.append(_source_type(action["digitalSourceType"]))
        signer = (active.get("signature_info") or {}).get("issuer")
        untrusted = any(s.get("code") == "signingCredential.untrusted" for s in store.get("validation_status") or [])
        if state == "Valid" and untrusted:
            state = "Valid (signer not on a trust list)"
        return codes, str(state) if state else None, signer
    finally:
        reader.close()


def read_iptc(data: bytes) -> list[str]:
    """DigitalSourceType codes in any embedded XMP packet (unsigned)."""
    return [m.decode() for m in _IPTC_PATTERN.findall(data)]


def assess(data: bytes, mime: str) -> Provenance:
    """Decide the label from the original file bytes."""
    codes, state, signer = read_c2pa(data, mime)
    if state is not None:
        signed_by = f" Signed by {signer}." if signer else ""
        if state.startswith("Invalid"):
            return Provenance(
                "unknown",
                "This file has Content Credentials, but they failed validation (the file may have been edited after signing), so they can't be trusted.",
                [Evidence("C2PA", "validation state", state)],
            )
        evidence = [Evidence("C2PA", "c2pa.actions → digitalSourceType", c, note=f"signature: {state}") for c in codes]
        if any(c in AI_SOURCE_TYPES for c in codes):
            return Provenance("ai_generated", f"Its Content Credentials (C2PA) say it was made with generative AI.{signed_by}", evidence)
        if any(c in CAPTURE_SOURCE_TYPES for c in codes):
            return Provenance("human_verified", f"Its Content Credentials (C2PA) say it was captured by a camera.{signed_by}", evidence)

    iptc = read_iptc(data)
    if any(c in AI_SOURCE_TYPES for c in iptc):
        return Provenance(
            "ai_generated",
            "Its IPTC metadata declares an AI source (DigitalSourceType).",
            [Evidence("IPTC", "Iptc4xmpExt:DigitalSourceType", c) for c in iptc],
        )
    if any(c in CAPTURE_SOURCE_TYPES for c in iptc):
        return Provenance(
            "unknown",
            "Its IPTC metadata claims a camera capture, but the claim isn't signed, so it can't be verified.",
            [Evidence("IPTC", "Iptc4xmpExt:DigitalSourceType", c, note="unsigned") for c in iptc],
        )
    return Provenance("unknown", "No provenance metadata (Content Credentials or IPTC source type) was found. MoodBoards never guesses from pixels.")
