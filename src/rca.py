"""
rca.py
------
L2 Stage 1 + Stage 2

Stage 1 — Enhance incident summaries with:
    BlastRadius     : distinct affected systems × avg CoIF per event (normalised 0-100)
    ImpactTier      : CRITICAL / HIGH / MEDIUM / LOW (percentile-based on TotalCoIF)
    CorrelationStrength : which L1 signals fired (based on incident metadata)

Stage 2 — Root Cause Analysis:
    Chronic vs. Event classification driven by real event frequency data
    Root cause interface / system identification
    Confidence score + human-readable narrative

Classification logic (all deterministic, data-driven):
    CHRONIC          → same ErrorCode + InterfaceID appeared ≥3 times across the dataset
                        AND the incident spans a time window > CHRONIC_DURATION_MIN
    EVENT            → incident duration ≤ EVENT_BURST_MIN AND ≤ EVENT_MAX_EVENTS events
                        AND single interface involved
    CHRONIC_EVENT    → mixed: recurring pattern but surfaced as a short burst
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import networkx as nx
from typing import Optional

# ---------------------------------------------------------------------------
# Tuneable thresholds
# ---------------------------------------------------------------------------
CHRONIC_RECURRENCE_MIN: int = 3          # times same ErrorCode+InterfaceID must appear
CHRONIC_DURATION_MIN: int = 30           # minutes: incident span > this → lean CHRONIC
EVENT_BURST_MIN: int = 30                # minutes: incident span ≤ this → lean EVENT
EVENT_MAX_EVENTS: int = 8                # events: <= this count → lean EVENT
CONFIDENCE_HIGH: float = 0.85
CONFIDENCE_MED: float = 0.65
CONFIDENCE_LOW: float = 0.50


# ---------------------------------------------------------------------------
# Stage 1: Blast-Radius + ImpactTier
# ---------------------------------------------------------------------------

def enhance_incidents(
    incidents_df: pd.DataFrame,
    enriched_events: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add BlastRadius, ImpactTier, and CorrelationStrength to incidents_df.
    Returns a NEW dataframe — incidents_df is never mutated.
    """
    if incidents_df.empty:
        return incidents_df.copy()

    df = incidents_df.copy()

    # --- BlastRadius ---
    # distinct systems affected × (TotalCoIF / EventCount), normalised 0-100
    df["_n_systems"] = df["AffectedSystems"].apply(
        lambda s: len(s) if isinstance(s, list) else 1
    )
    df["_avg_coif_per_event"] = df["TotalCoIF"] / df["EventCount"].clip(lower=1)
    raw_blast = df["_n_systems"] * df["_avg_coif_per_event"]
    max_blast = raw_blast.max() if raw_blast.max() > 0 else 1
    df["BlastRadius"] = (raw_blast / max_blast * 100).round(1)

    # --- ImpactTier (percentile on TotalCoIF) ---
    p90 = df["TotalCoIF"].quantile(0.90)
    p70 = df["TotalCoIF"].quantile(0.70)
    p40 = df["TotalCoIF"].quantile(0.40)

    def _tier(coif: float) -> str:
        if coif >= p90:
            return "CRITICAL"
        elif coif >= p70:
            return "HIGH"
        elif coif >= p40:
            return "MEDIUM"
        return "LOW"

    df["ImpactTier"] = df["TotalCoIF"].apply(_tier)

    # --- CorrelationStrength (infer from incident metadata) ---
    def _corr_strength(row: pd.Series) -> str:
        signals = []
        # Event count indicates temporal clustering
        if row["EventCount"] >= 5:
            signals.append("TEMPORAL")
        # Multiple systems → dependency correlation fired
        if row["_n_systems"] >= 3:
            signals.append("DEPENDENCY")
        # Same error code → error correlation fired
        if row["PrimaryErrorCode"] != "N/A":
            signals.append("ERROR_CLASS")
        # If we see just 1 system but many events → strong session/request correlation
        if row["_n_systems"] == 1 and row["EventCount"] >= 3:
            signals.append("SESSION")
        return " + ".join(signals) if signals else "TEMPORAL"

    df["CorrelationStrength"] = df.apply(_corr_strength, axis=1)

    # cleanup helper cols
    df.drop(columns=["_n_systems", "_avg_coif_per_event"], inplace=True)

    return df


# ---------------------------------------------------------------------------
# Stage 2: RCA Engine
# ---------------------------------------------------------------------------

def _build_recurrence_index(enriched_events: pd.DataFrame) -> pd.Series:
    """
    Count occurrences of each (InterfaceID, ErrorCode) pair across the entire
    dataset. Returns a Series indexed by (InterfaceID, ErrorCode).
    """
    if enriched_events.empty:
        return pd.Series(dtype=int)
    counts = (
        enriched_events
        .groupby(["InterfaceID", "ErrorCode"])
        .size()
    )
    return counts


def _classify_single_incident(
    inc_row: pd.Series,
    recurrence_idx: pd.Series,
    enriched_events: pd.DataFrame,
) -> dict:
    """
    Classify one incident row into CHRONIC / EVENT / CHRONIC_EVENT and
    produce root cause info.
    """
    inc_id = inc_row["IncidentID"]

    # ---- Duration ----
    try:
        start = pd.Timestamp(inc_row["StartTime"])
        end   = pd.Timestamp(inc_row["EndTime"])
        duration_min = max((end - start).total_seconds() / 60, 0.1)
    except Exception:
        duration_min = 0.0

    # ---- Recurrence of primary error on primary interface ----
    primary_error = inc_row.get("PrimaryErrorCode", "N/A")
    affected_ifaces: list = inc_row.get("AffectedInterfaces", [])
    if not isinstance(affected_ifaces, list):
        affected_ifaces = [str(affected_ifaces)]

    # Sum recurrence counts across all affected interfaces
    total_recurrence = 0
    dominant_iface = affected_ifaces[0] if affected_ifaces else "UNKNOWN"
    dominant_recurrence = 0
    for iface in affected_ifaces:
        try:
            r = recurrence_idx.get((iface, primary_error), 0)
        except Exception:
            r = 0
        total_recurrence += r
        if r > dominant_recurrence:
            dominant_recurrence = r
            dominant_iface = iface

    n_ifaces = len(affected_ifaces)
    n_events = int(inc_row.get("EventCount", 1))

    # ---- Classification ----
    is_chronic_recurrence = total_recurrence >= CHRONIC_RECURRENCE_MIN
    is_chronic_duration   = duration_min > CHRONIC_DURATION_MIN
    is_event_burst        = (duration_min <= EVENT_BURST_MIN
                             and n_events <= EVENT_MAX_EVENTS
                             and n_ifaces == 1)

    if is_chronic_recurrence and is_event_burst:
        category = "CHRONIC_EVENT"
        confidence = CONFIDENCE_MED
    elif is_chronic_recurrence or is_chronic_duration:
        category = "CHRONIC"
        confidence = CONFIDENCE_HIGH if is_chronic_recurrence else CONFIDENCE_MED
    elif is_event_burst:
        category = "EVENT"
        confidence = CONFIDENCE_HIGH
    else:
        # Moderate size, some recurrence
        if total_recurrence >= 2:
            category = "CHRONIC"
            confidence = CONFIDENCE_MED
        else:
            category = "EVENT"
            confidence = CONFIDENCE_LOW

    # ---- Root cause system / interface ----
    # The interface with the highest individual CoIF contribution is the root
    if "IncidentID" in enriched_events.columns:
        inc_events = enriched_events[enriched_events["IncidentID"] == inc_id]
    else:
        inc_events = enriched_events[
            enriched_events["InterfaceID"].isin(affected_ifaces)
        ]

    root_cause_iface = dominant_iface
    root_cause_system = "UNKNOWN"

    if not inc_events.empty:
        iface_coif = (
            inc_events.groupby("InterfaceID")["CoIF"]
            .sum()
            .sort_values(ascending=False)
        )
        if not iface_coif.empty:
            root_cause_iface = iface_coif.index[0]
            rc_rows = inc_events[inc_events["InterfaceID"] == root_cause_iface]
            if not rc_rows.empty:
                root_cause_system = rc_rows.iloc[0].get("SourceSystem", "UNKNOWN")

    # ---- Narrative ----
    narrative = _build_narrative(
        inc_id, category, confidence, primary_error,
        root_cause_iface, root_cause_system,
        total_recurrence, duration_min, n_events
    )

    # ---- Supporting evidence ----
    supporting_events: list[str] = []
    if not inc_events.empty:
        failed = inc_events[inc_events["Status"] == "Failed"]["EventID"].tolist()
        supporting_events = failed[:5] if failed else inc_events["EventID"].tolist()[:5]

    return {
        "IncidentID":           inc_id,
        "RCACategory":          category,
        "ConfidenceScore":      round(confidence, 2),
        "PrimaryRootCause":     f"{primary_error} on {root_cause_iface}",
        "RootCauseSystem":      root_cause_system,
        "RootCauseInterface":   root_cause_iface,
        "RecurrenceCount":      int(total_recurrence),
        "IncidentDuration_min": round(duration_min, 1),
        "SupportingEvents":     supporting_events,
        "RCANarrative":         narrative,
    }


def _build_narrative(
    inc_id: str,
    category: str,
    confidence: float,
    error_code: str,
    iface: str,
    system: str,
    recurrence: int,
    duration_min: float,
    n_events: int,
) -> str:
    pct = int(confidence * 100)

    if category == "CHRONIC":
        return (
            f"**{inc_id}** is classified as a **CHRONIC** issue ({pct}% confidence). "
            f"The error `{error_code}` has occurred **{recurrence} times** on interface "
            f"`{iface}` (system: `{system}`) across the dataset, indicating a recurring "
            f"structural problem rather than a one-off spike. "
            f"The incident spanned **{duration_min:.0f} minutes** with {n_events} events. "
            f"Recommend a root-cause fix rather than a restart."
        )
    elif category == "EVENT":
        return (
            f"**{inc_id}** is classified as a **TRANSIENT EVENT** ({pct}% confidence). "
            f"The error `{error_code}` on `{iface}` produced {n_events} events "
            f"in a short {duration_min:.0f}-minute window with low historical recurrence "
            f"({recurrence} prior occurrences). "
            f"Likely a temporary external or environmental failure. "
            f"Monitor for recurrence before escalating."
        )
    else:  # CHRONIC_EVENT
        return (
            f"**{inc_id}** shows a **MIXED CHRONIC + EVENT** pattern ({pct}% confidence). "
            f"The error `{error_code}` on `{iface}` has appeared {recurrence} times "
            f"historically but this burst is short ({duration_min:.0f} min, {n_events} events). "
            f"A known chronic weakness may be periodically manifesting under load. "
            f"Requires both immediate triage AND a long-term structural fix."
        )


def classify_incidents(
    incidents_df: pd.DataFrame,
    enriched_events: pd.DataFrame,
    G: Optional[nx.DiGraph] = None,
) -> pd.DataFrame:
    """
    Main entry point for Stage 2.

    Parameters
    ----------
    incidents_df    : enhanced incidents (output of enhance_incidents)
    enriched_events : events with IncidentID assigned (L1 pipeline output)
    G               : dependency graph (optional, reserved for future use)

    Returns
    -------
    rca_df  — one row per incident with RCA fields
    """
    if incidents_df.empty:
        return pd.DataFrame()

    recurrence_idx = _build_recurrence_index(enriched_events)

    rows = []
    for _, row in incidents_df.iterrows():
        rows.append(_classify_single_incident(row, recurrence_idx, enriched_events))

    rca_df = pd.DataFrame(rows)

    # Merge ImpactTier + BlastRadius from enhanced incidents
    tier_cols = ["IncidentID", "ImpactTier", "BlastRadius", "TotalCoIF",
                 "EventCount", "AffectedSystems", "AffectedInterfaces",
                 "PrimaryErrorCode", "PrimaryRootCauseClass"]
    available_tier_cols = [c for c in tier_cols if c in incidents_df.columns]
    rca_df = rca_df.merge(
        incidents_df[available_tier_cols],
        on="IncidentID",
        how="left",
    )

    return rca_df.sort_values("TotalCoIF", ascending=False).reset_index(drop=True)
