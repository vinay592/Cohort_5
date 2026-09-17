"""
coif.py
-------
Implements the Cost of Integration Failure (CoIF) formula:

    CoIF = FailureSignal × PriorityWeight × ProcessWeight × CostMultiplier

All intermediate components are stored in the dataframe for explainability.
"""

from __future__ import annotations

import pandas as pd
import os
from sklearn.linear_model import LinearRegression

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


# --- Train ML Model globally (once per load) ---
_train_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "coif_training_history_1.csv")
_train_df = pd.read_csv(_train_file)
_X_train = _train_df[["priority_weight", "process_impact_weight", "frequency", "close_calendar_multiplier"]]
_y_train = _train_df["CoIF"]

_ml_model = LinearRegression()
_ml_model.fit(_X_train, _y_train)

def compute_coif(df: pd.DataFrame, use_legacy: bool = False) -> pd.DataFrame:
    """
    Given an enriched dataframe (output of normalization.enrich),
    add FailureSignal and CoIF columns. Uses ML model to predict CoIF,
    or legacy scaled formula if requested.
    """
    df = df.copy()

    df["FailureSignal"] = df["Status"].map(FAILURE_SIGNAL)
    
    # 1) Enhanced Baseline Formula
    # Combine structural importance with event severity and calendar impact
    # Priority is 60% weight, Process is 40% weight
    structural_criticality = (df["PriorityWeight"] * 0.6) + (df["ProcessWeight"] * 0.4)
    
    # Cost multiplier boosts the score (e.g., 3.0 multiplier adds 50% penalty to severity)
    cost_factor = 1.0 + (df["CostMultiplier"] - 1.0) * 0.25 
    
    # Calculate base raw score
    raw_old = structural_criticality * df["FailureSignal"] * cost_factor
    
    # Cap naturally at 100 and ensure successes are 0
    df["OldFormulaCoIF"] = raw_old.clip(lower=0, upper=100.0)
    df.loc[df["FailureSignal"] == 0, "OldFormulaCoIF"] = 0.0

    # 2) ML Model
    X_pred = pd.DataFrame({
        "priority_weight": df["PriorityWeight"],
        "process_impact_weight": df["ProcessWeight"],
        "frequency": df["FailureSignal"].fillna(0),
        "close_calendar_multiplier": df["CostMultiplier"].fillna(1)
    })
    
    df["ML_CoIF"] = _ml_model.predict(X_pred)
    df["ML_CoIF"] = df["ML_CoIF"].clip(lower=0)
    df.loc[df["FailureSignal"] == 0, "ML_CoIF"] = 0.0

    # 3) Assign the final CoIF column
    if use_legacy:
        df["CoIF"] = df["OldFormulaCoIF"]
    else:
        df["CoIF"] = df["ML_CoIF"]

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
