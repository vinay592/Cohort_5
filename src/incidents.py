"""
incidents.py
------------
L1 incident correlation engine.

Correlation signals used (in order of strength):
    1. Strong  – same RequestID or same SessionID
    2. Temporal – events within ±TEMPORAL_WINDOW_MINUTES minutes of each other
    3. Dependency – events on interfaces connected in the system graph
    4. Error – same ErrorCode + RootCauseClass across nearby events

Algorithm:
    Union-Find (disjoint-set) over event indices to cluster them.
    Events connected by ANY of the signals above are merged into the same cluster.

Output:
    enriched_events with added 'IncidentID' column (e.g. "INC-0001")
    incidents_df with one summary row per cluster, ranked by TotalCoIF DESC
"""

from __future__ import annotations

from typing import List

import networkx as nx
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TEMPORAL_WINDOW_MINUTES: int = 5          # ±5 minutes
MIN_CLUSTER_SIZE: int = 1                 # include singleton events too


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------

class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # path compression
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


# ---------------------------------------------------------------------------
# Correlation helpers
# ---------------------------------------------------------------------------

def _strong_correlation(df: pd.DataFrame, uf: _UnionFind) -> None:
    """Merge events sharing the same RequestID or SessionID."""
    for col in ["RequestID", "SessionID"]:
        if col not in df.columns:
            continue
        groups = df.groupby(col).groups
        for grp_indices in groups.values():
            idxs = list(grp_indices)
            for i in range(1, len(idxs)):
                uf.union(idxs[0], idxs[i])


def _temporal_correlation(df: pd.DataFrame, uf: _UnionFind) -> None:
    """
    Merge events on the SAME interface within ±TEMPORAL_WINDOW_MINUTES.
    
    Restricting to the same interface prevents the transitive-chain problem
    where all events across the full dataset collapse into one giant cluster.
    """
    window = pd.Timedelta(minutes=TEMPORAL_WINDOW_MINUTES)

    for _iface, grp in df.dropna(subset=["Timestamp"]).groupby("InterfaceID"):
        grp_sorted = grp.sort_values("Timestamp")
        idxs = grp_sorted.index.tolist()
        ts_vals = grp_sorted["Timestamp"].tolist()

        left = 0
        for right in range(len(idxs)):
            while (
                left < right
                and (ts_vals[right] - ts_vals[left]) > window
            ):
                left += 1
            for i in range(left, right):
                uf.union(idxs[i], idxs[right])


def _dependency_correlation(
    df: pd.DataFrame, uf: _UnionFind, G: nx.DiGraph
) -> None:
    """
    Merge events that occur on directly connected interfaces
    (i.e. SourceSystem of one is TargetSystem of another) within
    the temporal window.
    """
    window = pd.Timedelta(minutes=TEMPORAL_WINDOW_MINUTES)

    # Build (system, idx, ts) list
    records = []
    for pos, (df_idx, row) in enumerate(df.iterrows()):
        records.append(
            {
                "pos": pos,
                "df_idx": df_idx,
                "src": row.get("SourceSystem"),
                "tgt": row.get("TargetSystem"),
                "ts": row.get("Timestamp"),
            }
        )

    for i, ri in enumerate(records):
        for j, rj in enumerate(records):
            if i >= j:
                continue
            if ri["ts"] is None or rj["ts"] is None:
                continue
            if abs(ri["ts"] - rj["ts"]) > window:
                continue
            # Check if edges are connected in the dependency graph
            # i.e. ri's target is rj's source or vice versa
            if G.has_node(ri["tgt"]) and G.has_node(rj["src"]):
                if G.has_edge(ri["tgt"], rj["src"]) or G.has_edge(rj["tgt"], ri["src"]):
                    uf.union(ri["df_idx"], rj["df_idx"])


def _error_correlation(df: pd.DataFrame, uf: _UnionFind) -> None:
    """
    Merge events with the same (ErrorCode, RootCauseClass) that occur
    within the temporal window.
    """
    window = pd.Timedelta(minutes=TEMPORAL_WINDOW_MINUTES)
    cols = ["ErrorCode", "RootCauseClass"]
    available = [c for c in cols if c in df.columns]
    if not available:
        return

    for key, group in df.groupby(available):
        group_sorted = group.sort_values("Timestamp")
        idxs = group_sorted.index.tolist()
        ts_vals = group_sorted["Timestamp"].tolist()
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                if ts_vals[j] - ts_vals[i] > window:
                    break
                uf.union(idxs[i], idxs[j])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def correlate_incidents(
    df: pd.DataFrame,
    G: nx.DiGraph | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Assign IncidentIDs to events and produce an incident summary dataframe.

    Parameters
    ----------
    df : enriched events dataframe (output of coif.compute_coif)
    G  : dependency graph (output of graph.build_dependency_graph); optional

    Returns
    -------
    (events_with_incidents, incidents_summary)
    """
    if df.empty:
        return df.copy(), pd.DataFrame()

    # Re-index to 0..N-1 integers for UnionFind
    df = df.reset_index(drop=True)
    uf = _UnionFind(len(df))

    _strong_correlation(df, uf)
    _temporal_correlation(df, uf)
    if G is not None:
        _dependency_correlation(df, uf, G)
    _error_correlation(df, uf)

    # Assign cluster IDs
    root_to_cluster: dict[int, int] = {}
    cluster_ids = []
    counter = 0
    for i in range(len(df)):
        root = uf.find(i)
        if root not in root_to_cluster:
            root_to_cluster[root] = counter
            counter += 1
        cluster_ids.append(root_to_cluster[root])

    df = df.copy()
    df["_cluster"] = cluster_ids
    df["IncidentID"] = df["_cluster"].apply(lambda c: f"INC-{c + 1:04d}")

    # Build incident summary
    summaries: list[dict] = []
    for cluster_id, group in df.groupby("_cluster"):
        inc_id = f"INC-{cluster_id + 1:04d}"
        summaries.append(
            {
                "IncidentID": inc_id,
                "StartTime": group["Timestamp"].min(),
                "EndTime": group["Timestamp"].max(),
                "EventCount": len(group),
                "AffectedInterfaces": sorted(group["InterfaceID"].unique().tolist()),
                "AffectedSystems": sorted(
                    set(group["SourceSystem"].tolist() + group["TargetSystem"].tolist())
                ),
                "PrimaryErrorCode": group["ErrorCode"].mode().iloc[0]
                if not group["ErrorCode"].mode().empty
                else "N/A",
                "PrimaryRootCauseClass": group["RootCauseClass"].mode().iloc[0]
                if "RootCauseClass" in group and not group["RootCauseClass"].mode().empty
                else "N/A",
                "TotalCoIF": group["CoIF"].sum(),
                "MaxCoIF": group["CoIF"].max(),
            }
        )

    incidents_df = pd.DataFrame(summaries).sort_values("TotalCoIF", ascending=False).reset_index(drop=True)

    df.drop(columns=["_cluster"], inplace=True)
    return df, incidents_df
