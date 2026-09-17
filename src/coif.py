"""
coif.py
-------
Implements the Cost of Integration Failure (CoIF) formula:

    CoIF = FailureSignal × PriorityWeight × ProcessWeight × CostMultiplier

All intermediate components are stored in the dataframe for explainability.
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Configurable failure signal mapping – change here, not scattered in code
# ---------------------------------------------------------------------------
FAILURE_SIGNAL: dict[str, float] = {
    "Failed": 1.0,
    "Warning": 0.5,
    "Retry": 0.3,
    "Success": 0.0,
}


def compute_failure_signal(status: str) -> float:
    """
    Return the FailureSignal for a given event Status.
    Unknown statuses return NaN so they are not silently treated as failures.
    """
    return FAILURE_SIGNAL.get(status, float("nan"))


def compute_coif(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given an enriched dataframe (output of normalization.enrich),
    add FailureSignal and CoIF columns.

    Intermediate columns preserved:
        FailureSignal, PriorityWeight, ProcessWeight, CostMultiplier, CoIF
    """
    df = df.copy()

    df["FailureSignal"] = df["Status"].map(FAILURE_SIGNAL)

    df["CoIF"] = (
        df["FailureSignal"]
        * df["PriorityWeight"]
        * df["ProcessWeight"]
        * df["CostMultiplier"]
    )

    return df


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _base_agg(df: pd.DataFrame, group_col: str | list[str]) -> pd.DataFrame:
    agg = (
        df.groupby(group_col)
        .agg(
            TotalCoIF=("CoIF", "sum"),
            EventCount=("EventID", "count"),
            FailedCount=("Status", lambda s: (s == "Failed").sum()),
            WarningCount=("Status", lambda s: (s == "Warning").sum()),
            AvgLatency_ms=("Latency_ms", "mean"),
            SLA_Violations=("SLA_Violation", "sum"),
            MaxCoIF=("CoIF", "max"),
        )
        .reset_index()
        .sort_values("TotalCoIF", ascending=False)
    )
    return agg


def aggregate_by_interface(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per InterfaceID, ranked by TotalCoIF DESC."""
    agg = _base_agg(df, "InterfaceID")

    # Attach interface metadata from the first row of each group
    meta = (
        df[
            [
                "InterfaceID", "SourceSystem", "TargetSystem",
                "BusinessProcess", "Priority", "Area",
                "PriorityWeight", "ProcessWeight",
                "FailureSignal", "CostMultiplier", "WindowType",
            ]
        ]
        .drop_duplicates("InterfaceID")
        .set_index("InterfaceID")
    )

    agg = agg.merge(meta, on="InterfaceID", how="left")
    agg["Rank"] = range(1, len(agg) + 1)
    return agg


def aggregate_by_process(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per BusinessProcess, ranked by TotalCoIF DESC."""
    return _base_agg(df, "BusinessProcess")


def aggregate_by_system(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate by SourceSystem (i.e. the system originating the failure),
    ranked by TotalCoIF DESC.
    """
    agg = _base_agg(df, "SourceSystem")
    agg.rename(columns={"SourceSystem": "System"}, inplace=True)
    return agg
