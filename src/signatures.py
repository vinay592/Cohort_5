"""
signatures.py
-------------
Generate deterministic de-duplication signatures for events.

A SHA-256 hash is computed from:
    InterfaceID + Status + ErrorCode + RootCauseClass + normalized(ErrorText)

Duplicate events share the same Signature.
DuplicateCount is added so repeated patterns can be surfaced without
removing the original events (raw event count is preserved).
"""

from __future__ import annotations

import hashlib
import re

import pandas as pd


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

_VOLATILE_PATTERNS = [
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",  # UUIDs
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b",  # ISO timestamps
    r"\b(?:EVT|SESS|REQ)_[A-Za-z0-9]+\b",  # event/session/request IDs
    r"\b\d+\b",  # bare numbers (e.g. latency values in messages)
]

_VOLATILE_RE = re.compile("|".join(_VOLATILE_PATTERNS), re.IGNORECASE)


def _normalize_text(text: str) -> str:
    """Lowercase, strip, and remove volatile tokens from error text."""
    if not isinstance(text, str):
        return ""
    text = text.lower().strip()
    text = _VOLATILE_RE.sub(" <VAL> ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _make_signature(row: pd.Series) -> str:
    """Compute SHA-256 signature for a single event row."""
    parts = [
        str(row.get("InterfaceID", "")),
        str(row.get("Status", "")),
        str(row.get("ErrorCode", "")),
        str(row.get("RootCauseClass", "")),
        _normalize_text(str(row.get("ErrorText", ""))),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_signatures(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add Signature and DuplicateCount columns to the enriched events dataframe.

    Signature       – 16-char hex prefix of SHA-256 hash
    DuplicateCount  – how many events share this signature
    NormErrorText   – normalized error text (for inspection)
    """
    df = df.copy()

    df["NormErrorText"] = df.get("ErrorText", pd.Series("", index=df.index)).apply(
        _normalize_text
    )
    df["Signature"] = df.apply(_make_signature, axis=1)

    sig_counts = df.groupby("Signature")["EventID"].transform("count")
    df["DuplicateCount"] = sig_counts

    return df
