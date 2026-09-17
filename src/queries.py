"""
queries.py
----------
Deterministic Q&A query engine for the "Ask the Data" panel.

All numerical answers are derived from actual dataframes; no facts are invented.
NL pattern matching routes questions to the appropriate query function.
Each answer includes an Evidence section with supporting event IDs / rows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd


# ---------------------------------------------------------------------------
# Answer container
# ---------------------------------------------------------------------------

@dataclass
class Answer:
    question: str
    answer: str
    evidence_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    evidence_label: str = "Supporting Events"


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def _top_coif_interface(
    df: pd.DataFrame,
    interface_agg: pd.DataFrame,
    n: int = 1,
) -> Answer:
    top = interface_agg.nlargest(n, "TotalCoIF")
    parts = []
    for _, row in top.iterrows():
        iface = row["InterfaceID"]
        proc = row.get("BusinessProcess", "?")
        pw = row.get("PriorityWeight", "?")
        piw = row.get("ProcessWeight", "?")
        cm = row.get("CostMultiplier", "?")
        fs = row.get("FailureSignal", "?")
        coif = row["TotalCoIF"]
        try:
            single_coif = float(fs) * float(pw) * float(piw) * float(cm)
            formula = f"{fs} × {pw} × {piw} × {cm} = {single_coif:,.0f} (per event max)"
        except (ValueError, TypeError):
            formula = f"{fs} × {pw} × {piw} × {cm} = ? (per event max)"
        parts.append(
            f"**{iface}** has the highest Total CoIF = **{coif:,.0f}**\n\n"
            f"- Business Process: {proc}\n"
            f"- Failure Signal: {fs}\n"
            f"- Priority Weight: {pw}\n"
            f"- Process Weight: {piw}\n"
            f"- Calendar Multiplier: {cm}\n"
            f"- CoIF formula: {formula}"
        )
    evidence = df[df["InterfaceID"].isin(top["InterfaceID"])].head(50)
    return Answer(
        question="Which interface has the highest CoIF?",
        answer="\n\n".join(parts),
        evidence_df=evidence,
        evidence_label="Events for top interface(s)",
    )


def _explain_ranking(
    df: pd.DataFrame,
    interface_agg: pd.DataFrame,
    iface_a: str,
    iface_b: str,
) -> Answer:
    row_a = interface_agg[interface_agg["InterfaceID"] == iface_a]
    row_b = interface_agg[interface_agg["InterfaceID"] == iface_b]

    def _fmt_row(row: pd.DataFrame, name: str) -> str:
        if row.empty:
            return f"**{name}** not found in data."
        r = row.iloc[0]
        return (
            f"**{name}**: CoIF = {r['TotalCoIF']:,.0f}  "
            f"(PW={r.get('PriorityWeight','?')} × ProcessW={r.get('ProcessWeight','?')} "
            f"× CM={r.get('CostMultiplier','?')})"
        )

    answer = f"{_fmt_row(row_a, iface_a)}\n\n{_fmt_row(row_b, iface_b)}"
    evidence = df[df["InterfaceID"].isin([iface_a, iface_b])].head(50)
    return Answer(
        question=f"Why is {iface_a} ranked above {iface_b}?",
        answer=answer,
        evidence_df=evidence,
    )


def _most_impacted_systems(
    df: pd.DataFrame,
    system_agg: pd.DataFrame,
    n: int = 5,
) -> Answer:
    top = system_agg.nlargest(n, "TotalCoIF")
    lines = [
        f"{i+1}. **{row['System']}** – Total CoIF {row['TotalCoIF']:,.0f}, "
        f"Events {row['EventCount']}, Failed {row['FailedCount']}"
        for i, (_, row) in enumerate(top.iterrows())
    ]
    answer = "**Top systems by business impact (Total CoIF):**\n\n" + "\n\n".join(lines)
    evidence = df[df["SourceSystem"].isin(top["System"])].head(50)
    return Answer(
        question="Which systems are most impacted?",
        answer=answer,
        evidence_df=evidence,
        evidence_label="Events from top systems",
    )


def _failures_during_window(
    df: pd.DataFrame,
    window_type: str,
) -> Answer:
    subset = df[df["WindowType"].str.upper() == window_type.upper()]
    answer = (
        f"**{len(subset)} event(s)** occurred during **{window_type}** windows.\n\n"
        f"- Failed: {(subset['Status'] == 'Failed').sum()}\n"
        f"- Warning: {(subset['Status'] == 'Warning').sum()}\n"
        f"- Total CoIF: {subset['CoIF'].sum():,.0f}\n"
        f"- Unique Interfaces: {subset['InterfaceID'].nunique()}"
    )
    return Answer(
        question=f"Which failures occurred during {window_type}?",
        answer=answer,
        evidence_df=subset.head(50),
        evidence_label=f"Events during {window_type}",
    )


def _top_incidents(
    df: pd.DataFrame,
    incidents_df: pd.DataFrame,
    n: int = 5,
) -> Answer:
    top = incidents_df.nlargest(n, "TotalCoIF")
    lines = []
    for i, (_, row) in enumerate(top.iterrows()):
        lines.append(
            f"{i+1}. **{row['IncidentID']}** – CoIF {row['TotalCoIF']:,.0f}, "
            f"Events {row['EventCount']}, Systems: {', '.join(row['AffectedSystems'])}"
        )
    answer = f"**Top {n} incidents by business impact:**\n\n" + "\n\n".join(lines)
    top_ids = top["IncidentID"].tolist()
    evidence = df[df.get("IncidentID", pd.Series(dtype=str)).isin(top_ids)].head(50)
    return Answer(
        question=f"Top {n} incidents by business impact?",
        answer=answer,
        evidence_df=evidence,
        evidence_label="Events from top incidents",
    )


def _sla_violations(
    df: pd.DataFrame,
    interface_agg: pd.DataFrame,
) -> Answer:
    top = interface_agg.nlargest(5, "SLA_Violations")[
        ["InterfaceID", "SLA_Violations", "TotalCoIF"]
    ]
    lines = [
        f"{i+1}. **{row['InterfaceID']}** – {int(row['SLA_Violations'])} violations, "
        f"CoIF {row['TotalCoIF']:,.0f}"
        for i, (_, row) in enumerate(top.iterrows())
    ]
    answer = "**Top interfaces by SLA violations:**\n\n" + "\n\n".join(lines)
    evidence = df[df["SLA_Violation"] == 1].head(50)
    return Answer(
        question="Which interface has the most SLA violations?",
        answer=answer,
        evidence_df=evidence,
        evidence_label="SLA-violating events",
    )


def _system_filter(df: pd.DataFrame, system: str) -> Answer:
    subset = df[
        (df["SourceSystem"].str.upper() == system.upper())
        | (df["TargetSystem"].str.upper() == system.upper())
    ]
    answer = (
        f"**{len(subset)} event(s)** involve system **{system.upper()}**.\n\n"
        f"- Failed: {(subset['Status'] == 'Failed').sum()}\n"
        f"- Warning: {(subset['Status'] == 'Warning').sum()}\n"
        f"- Total CoIF: {subset['CoIF'].sum():,.0f}"
    )
    return Answer(
        question=f"Show all failures affecting {system.upper()}",
        answer=answer,
        evidence_df=subset.head(50),
        evidence_label=f"Events involving {system.upper()}",
    )


def _interface_detail(
    df: pd.DataFrame,
    interface_agg: pd.DataFrame,
    iface_id: str,
) -> Answer:
    row = interface_agg[interface_agg["InterfaceID"] == iface_id]
    if row.empty:
        return Answer(
            question=f"Why is {iface_id} high priority?",
            answer=f"Interface **{iface_id}** was not found in the dataset.",
        )
    r = row.iloc[0]
    try:
        single_coif = float(r.get('FailureSignal', 0)) * float(r.get('PriorityWeight', 0)) * float(r.get('ProcessWeight', 0)) * float(r.get('CostMultiplier', 0))
        formula = f"{r.get('FailureSignal','?')} × {r.get('PriorityWeight','?')} × {r.get('ProcessWeight','?')} × {r.get('CostMultiplier','?')} = {single_coif:,.0f} (per event max)"
    except (ValueError, TypeError):
        formula = f"{r.get('FailureSignal','?')} × {r.get('PriorityWeight','?')} × {r.get('ProcessWeight','?')} × {r.get('CostMultiplier','?')} = ? (per event max)"
    answer = (
        f"**Interface: {iface_id}**\n\n"
        f"- Business Process: {r.get('BusinessProcess', 'N/A')}\n"
        f"- Priority: {r.get('Priority', 'N/A')}\n"
        f"- Priority Weight: {r.get('PriorityWeight', 'N/A')}\n"
        f"- Process Weight: {r.get('ProcessWeight', 'N/A')}\n"
        f"- Calendar Multiplier: {r.get('CostMultiplier', 'N/A')}\n"
        f"- Failure Signal: {r.get('FailureSignal', 'N/A')}\n"
        f"\n**Total CoIF = {r['TotalCoIF']:,.0f}** {formula}"
    )
    evidence = df[df["InterfaceID"] == iface_id].head(50)
    return Answer(
        question=f"Why is {iface_id} high priority?",
        answer=answer,
        evidence_df=evidence,
    )


# ---------------------------------------------------------------------------
# Pattern-based router
# ---------------------------------------------------------------------------

_SYSTEM_CODES = ["ORD", "MFG", "PRC", "ASM", "DLV", "PAY"]


def answer_question(
    question: str,
    df: pd.DataFrame,
    interface_agg: pd.DataFrame,
    system_agg: pd.DataFrame,
    incidents_df: pd.DataFrame,
) -> Answer:
    """
    Route a natural-language question to the appropriate deterministic query.
    Returns an Answer with text and supporting evidence rows.
    """
    q = question.lower().strip()

    # Highest CoIF interface
    if re.search(r"highest coif|top interface|which interface.*coif", q):
        return _top_coif_interface(df, interface_agg, n=1)

    # Top N interfaces
    m = re.search(r"top\s+(\d+)\s+interface", q)
    if m:
        return _top_coif_interface(df, interface_agg, n=int(m.group(1)))

    # SLA violations
    if re.search(r"sla\s*violation", q):
        return _sla_violations(df, interface_agg)

    # Incidents
    if re.search(r"incident|top.*impact", q):
        m2 = re.search(r"top\s+(\d+)", q)
        n = int(m2.group(1)) if m2 else 5
        return _top_incidents(df, incidents_df, n=n)

    # Calendar window
    for wtype in ["qec", "mec", "normal"]:
        if wtype in q:
            return _failures_during_window(df, wtype.upper())
    if re.search(r"quarter.?end|close\s*period", q):
        return _failures_during_window(df, "QEC")
    if re.search(r"month.?end", q):
        return _failures_during_window(df, "MEC")

    # System impact
    if re.search(r"most impacted|impacted system|system.*affect", q):
        return _most_impacted_systems(df, system_agg)

    # System-specific filter
    for sys_code in _SYSTEM_CODES:
        if sys_code.lower() in q:
            return _system_filter(df, sys_code)

    # Interface detail (e.g. IF_PAY_001)
    m3 = re.search(r"(IF_[A-Z]{2,5}_\d{3})", question, re.IGNORECASE)
    if m3:
        iface = m3.group(1).upper()
        return _interface_detail(df, interface_agg, iface)

    # Payment vs stock comparison (example from spec)
    if re.search(r"payment.*stock|stock.*payment|why.*rank|rank.*above", q):
        return _explain_ranking(df, interface_agg, "IF_PAY_001", "IF_MFG_003")

    # Fallback
    return Answer(
        question=question,
        answer=(
            "I couldn't match your question to a specific query template.\n\n"
            "Try questions like:\n"
            "- *Which interface has the highest CoIF?*\n"
            "- *Top 5 incidents by business impact*\n"
            "- *Which failures occurred during QEC?*\n"
            "- *Which systems are most impacted?*\n"
            "- *Which interface has the most SLA violations?*\n"
            "- *Show me all failures affecting PAY*\n"
            "- *Why is IF_PAY_001 high priority?*"
        ),
        evidence_df=pd.DataFrame(),
    )
