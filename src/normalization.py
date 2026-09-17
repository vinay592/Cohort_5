"""
normalization.py
----------------
Join all reference tables to produce an enriched events dataframe with:
  - interface metadata (from interface_master)
  - priority weight (from priority_weight)
  - process impact weight (from process_impact_weight)
  - calendar multiplier (from business_calendar, via timestamp interval lookup)

All intermediate columns are preserved for explainability.
"""

from __future__ import annotations

import pandas as pd

from src.data_loader import DataBundle


def _lookup_calendar_multiplier(
    timestamps: pd.Series,
    calendar: pd.DataFrame,
) -> pd.Series:
    """
    For each event timestamp, find the matching business_calendar row
    and return its CostMultiplier.

    Handles:
    - No match → defaults to the "Normal" multiplier (1.0)
    - Multiple overlapping windows → raises a warning and picks the
      highest-cost multiplier (conservative/explicit choice).
    """
    # Build a simple lookup list (calendar is tiny)
    rows = calendar.to_dict("records")
    normal_multiplier = 1.0

    # Find the default Normal multiplier if present
    for row in rows:
        if row["WindowType"] == "Normal":
            normal_multiplier = row["CostMultiplier"]
            break

    def _lookup_single(ts: pd.Timestamp):
        if pd.isna(ts):
            return normal_multiplier

        matches = [
            row for row in rows
            if not pd.isna(row["WindowStart"])
            and not pd.isna(row["WindowEnd"])
            and row["WindowStart"] <= ts <= row["WindowEnd"]
        ]

        if not matches:
            return normal_multiplier
        if len(matches) == 1:
            return matches[0]["CostMultiplier"]

        # Multiple overlapping windows – conservative: pick highest cost
        # (This is surfaced as a validation warning by validation.py)
        return max(m["CostMultiplier"] for m in matches)

    return timestamps.apply(_lookup_single)


def _lookup_window_type(
    timestamps: pd.Series,
    calendar: pd.DataFrame,
) -> pd.Series:
    """Return the WindowType label for display purposes."""
    rows = calendar.to_dict("records")

    def _lookup_single(ts: pd.Timestamp):
        if pd.isna(ts):
            return "Normal"
        matches = [
            row for row in rows
            if not pd.isna(row["WindowStart"])
            and not pd.isna(row["WindowEnd"])
            and row["WindowStart"] <= ts <= row["WindowEnd"]
        ]
        if not matches:
            return "Normal"
        # Pick the highest-cost window type
        return max(matches, key=lambda m: m["CostMultiplier"])["WindowType"]

    return timestamps.apply(_lookup_single)


def enrich(bundle: DataBundle) -> pd.DataFrame:
    """
    Return an enriched events dataframe ready for CoIF calculation.

    Columns added:
        SourceSystem_im, TargetSystem_im, BusinessProcess, Priority,
        Area, Criticality, SLA_ms, PriorityWeight,
        ProcessWeight, CostMultiplier, WindowType
    """
    events = bundle.events.copy()
    im = bundle.interface_master
    pw = bundle.priority_weight
    piw = bundle.process_impact_weight
    cal = bundle.business_calendar

    # ------------------------------------------------------------------
    # Step 1: Join interface_master (prefer authoritative metadata)
    # ------------------------------------------------------------------
    # Drop columns from events that exist in interface_master
    # (except InterfaceID which is the join key)
    im_cols_to_join = [
        "InterfaceID", "SourceSystem", "TargetSystem", "Middleware", "Pattern",
        "BusinessProcess", "Priority", "Area", "Criticality", "SLA_ms", "PriorityWeight",
    ]
    im_subset = im[im_cols_to_join].copy()

    # Remove conflicting columns from events before merge
    event_only_cols = [
        c for c in events.columns
        if c not in im_cols_to_join or c == "InterfaceID"
    ]
    enriched = events[event_only_cols].merge(
        im_subset,
        on="InterfaceID",
        how="left",
        suffixes=("_evt", ""),
    )

    # ------------------------------------------------------------------
    # Step 2: Join priority weight
    # ------------------------------------------------------------------
    pw_subset = pw[["Priority", "Weight"]].rename(columns={"Weight": "PriorityWeight_ref"})
    enriched = enriched.merge(pw_subset, on="Priority", how="left")
    # Use reference table weight as authoritative
    enriched["PriorityWeight"] = enriched["PriorityWeight_ref"].fillna(
        enriched.get("PriorityWeight", pd.Series(dtype=float))
    )
    enriched.drop(columns=["PriorityWeight_ref"], inplace=True, errors="ignore")

    # ------------------------------------------------------------------
    # Step 3: Join process impact weight
    # ------------------------------------------------------------------
    piw_subset = piw[["BusinessProcess", "ProcessWeight"]]
    enriched = enriched.merge(piw_subset, on="BusinessProcess", how="left")

    # ------------------------------------------------------------------
    # Step 4: Determine calendar multiplier + window type
    # ------------------------------------------------------------------
    enriched["CostMultiplier"] = _lookup_calendar_multiplier(
        enriched["Timestamp"], cal
    )
    enriched["WindowType"] = _lookup_window_type(enriched["Timestamp"], cal)

    # ------------------------------------------------------------------
    # Step 5: SLA violation flag
    # ------------------------------------------------------------------
    enriched["SLA_Violation"] = (
        enriched["Latency_ms"] > enriched["SLA_ms"]
    ).astype(int)

    return enriched
