"""
data_loader.py
--------------
Load all reference CSV files and cache them for the Streamlit session.
Returns a DataBundle dict so callers never read CSVs more than once.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Default data directory – looks next to this file's project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = _PROJECT_ROOT / "data"


# ---------------------------------------------------------------------------
# DataBundle – typed container for all loaded tables
# ---------------------------------------------------------------------------
@dataclass
class DataBundle:
    events: pd.DataFrame
    interface_master: pd.DataFrame
    priority_weight: pd.DataFrame
    process_impact_weight: pd.DataFrame
    business_calendar: pd.DataFrame
    # optional
    change_events: Optional[pd.DataFrame] = None
    escalation_routing: Optional[pd.DataFrame] = None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_events(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    return df


def _load_interface_master(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _load_priority_weight(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _load_process_impact_weight(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _load_business_calendar(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["WindowStart"] = pd.to_datetime(df["WindowStart"], errors="coerce")
    df["WindowEnd"] = pd.to_datetime(df["WindowEnd"], errors="coerce")
    # Make WindowEnd inclusive by extending to end-of-day
    df["WindowEnd"] = df["WindowEnd"] + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return df


def _load_optional(path: Path) -> Optional[pd.DataFrame]:
    if path.exists():
        return pd.read_csv(path)
    return None


# ---------------------------------------------------------------------------
# Public cached loader
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading datasets …")
def load_all(data_dir: str | None = None) -> DataBundle:
    """
    Load all required + optional CSV files.
    Decorated with st.cache_data so the files are read once per session.
    """
    base = Path(data_dir) if data_dir else DATA_DIR

    bundle = DataBundle(
        events=_load_events(base / "events.csv"),
        interface_master=_load_interface_master(base / "interface_master.csv"),
        priority_weight=_load_priority_weight(base / "priority_weight.csv"),
        process_impact_weight=_load_process_impact_weight(base / "process_impact_weight.csv"),
        business_calendar=_load_business_calendar(base / "business_calendar.csv"),
        change_events=_load_optional(base / "change_events.csv"),
        escalation_routing=_load_optional(base / "escalation_routing.csv"),
    )
    return bundle
