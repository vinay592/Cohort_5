"""
app.py
------
L1 Integration Health Monitoring – Streamlit Dashboard
Cost of Integration Failure (CoIF) Platform

Run:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Page config – must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Integration Health Monitor – CoIF L1",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

import pandas as pd

from src.data_loader import load_all
from src.validation import validate
from src.normalization import enrich

import importlib
import sys
import src.coif
import src.ui_helpers
importlib.reload(sys.modules['src.coif'])
importlib.reload(sys.modules['src.ui_helpers'])
from src.coif import compute_coif, aggregate_by_interface, aggregate_by_process, aggregate_by_system
from src.signatures import add_signatures
from src.incidents import correlate_incidents
from src.graph import build_dependency_graph, graph_to_plotly, get_edge_data
from src.queries import answer_question
from src.ui_helpers import (
    apply_dark_theme,
    page_header,
    kpi_card,
    coif_bar_chart,
    coif_treemap,
    coif_donut_chart,
    coif_sunburst,
    coif_bubble_chart,
    event_timeline,
    coif_explanation_card,
    priority_badge,
)

# ---------------------------------------------------------------------------
# Apply theme
# ---------------------------------------------------------------------------
apply_dark_theme()

# ---------------------------------------------------------------------------
# Load + process data (cached)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Processing CoIF pipeline …")
def build_pipeline(use_legacy=False):
    bundle = load_all()
    report = validate(bundle)
    enriched = enrich(bundle)
    scored = compute_coif(enriched, use_legacy=use_legacy)
    signed = add_signatures(scored)

    iface_agg = aggregate_by_interface(signed)
    proc_agg = aggregate_by_process(signed)
    sys_agg = aggregate_by_system(signed)

    G = build_dependency_graph(bundle.interface_master, signed)
    events_with_inc, incidents_df = correlate_incidents(signed, G)

    return {
        "bundle": bundle,
        "report": report,
        "events": events_with_inc,
        "iface_agg": iface_agg,
        "proc_agg": proc_agg,
        "sys_agg": sys_agg,
        "G": G,
        "incidents": incidents_df,
    }

# Provide a toggle before we build the pipeline
use_legacy = st.sidebar.toggle("Use Enhanced Baseline for CoIF", value=False, help="Uses the enhanced robust baseline formula (0-100) instead of the ML model", key="legacy_toggle")

data = build_pipeline(use_legacy=use_legacy)
bundle = data["bundle"]
report = data["report"]
events = data["events"]
iface_agg = data["iface_agg"]
proc_agg = data["proc_agg"]
sys_agg = data["sys_agg"]
G = data["G"]
incidents_df = data["incidents"]

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.markdown(
    """
    <div style="text-align:center; padding: 20px 0 10px 0;">
        <div style="font-size:2rem;">🔗</div>
        <div style="font-size:1rem; font-weight:700; color:#38bdf8; letter-spacing:0.05em;">
            Integration Health
        </div>
        <div style="font-size:0.7rem; color:#94a3b8; margin-top:2px;">
            CoIF L1 Platform
        </div>
    </div>
    <hr style="border-color:#1e3a5f; margin: 8px 0 16px 0;">
    """,
    unsafe_allow_html=True,
)

PAGE_ICONS = {
    "Overview": "🏠",
    "Health Map": "🗺️",
    "Dependency Graph": "🌐",
    "Incidents": "🚨",
    "Event Explorer": "🔍",
    "Ask the Data": "💬",
}
page = st.sidebar.radio(
    "Navigation",
    list(PAGE_ICONS.keys()),
    format_func=lambda p: f"{PAGE_ICONS[p]}  {p}",
)

# Validation status in sidebar
st.sidebar.markdown("<hr style='border-color:#1e3a5f;'>", unsafe_allow_html=True)
if report.is_clean:
    st.sidebar.success("✅ Data validation passed")
else:
    st.sidebar.error(f"❌ {len(report.errors)} validation error(s)")
    if report.warnings:
        st.sidebar.warning(f"⚠️ {len(report.warnings)} warning(s)")

with st.sidebar.expander("Data Validation Details", expanded=not report.is_clean):
    if report.errors:
        for e in report.errors:
            st.error(e)
    if report.warnings:
        for w in report.warnings:
            st.warning(w)
    if report.is_clean and not report.warnings:
        st.success("All referential integrity checks passed.")

st.sidebar.markdown(
    f"""
    <div style="color:#475569; font-size:0.7rem; text-align:center; margin-top:8px;">
        {len(events):,} events · {iface_agg['InterfaceID'].nunique()} interfaces
    </div>
    """,
    unsafe_allow_html=True,
)

# ===========================================================================
# PAGE: Overview
# ===========================================================================
if page == "Overview":
    page_header(
        "Integration Health Overview",
        subtitle="Real-time business-impact scoring across all integration interfaces.",
        icon="🏠",
    )

    # KPI row
    total_events = len(events)
    failed_count = (events["Status"] == "Failed").sum()
    warning_count = (events["Status"] == "Warning").sum()
    total_coif = events["CoIF"].sum()
    sla_violations = events["SLA_Violation"].sum()
    n_interfaces = events["InterfaceID"].nunique()
    n_systems = events["SourceSystem"].nunique()
    n_incidents = len(incidents_df)

    cols = st.columns(4)
    kpi_data = [
        ("Total Events", total_events, "📦"),
        ("Failed Events", failed_count, "❌"),
        ("Warning Events", warning_count, "⚠️"),
        ("Interfaces", n_interfaces, "🔗"),
        ("Systems Affected", n_systems, "🖥️"),
        ("Total CoIF", int(total_coif), "📊"),
        ("SLA Violations", int(sla_violations), "⏱️"),
        ("Correlated Incidents", n_incidents, "🚨"),
    ]
    for i, (label, val, icon) in enumerate(kpi_data):
        with cols[i % 4]:
            st.markdown(kpi_card(label, val, icon), unsafe_allow_html=True)
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # Charts row — purposeful layout
    col1, col2 = st.columns(2)
    with col1:
        # Primary operational chart: which interfaces are costing the most
        st.plotly_chart(
            coif_bar_chart(iface_agg, "InterfaceID", "Top Interfaces by Total CoIF"),
            use_container_width=True,
        )
    with col2:
        # Event status split — first question ops teams ask
        st.plotly_chart(
            coif_donut_chart(events),
            use_container_width=True,
        )

    col3, col4 = st.columns(2)
    with col3:
        st.plotly_chart(event_timeline(events), use_container_width=True)
    with col4:
        st.plotly_chart(
            coif_treemap(iface_agg, "InterfaceID", "CoIF Distribution by Interface"),
            use_container_width=True,
        )

    # Recent high-impact incidents
    st.markdown(
        f"<div class='gold-divider'></div>"
        "<div style='color:#c9a84c; font-size:0.7rem; text-transform:uppercase; "
        "letter-spacing:0.1em; font-weight:600; margin-bottom:10px;'>Top Incidents by Business Impact</div>",
        unsafe_allow_html=True,
    )
    if not incidents_df.empty:
        top_inc = incidents_df.head(5).copy()
        top_inc["AffectedSystems"] = top_inc["AffectedSystems"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else x
        )
        top_inc["AffectedInterfaces"] = top_inc["AffectedInterfaces"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else x
        )
        st.dataframe(
            top_inc[
                ["IncidentID", "StartTime", "EndTime", "EventCount",
                 "AffectedSystems", "TotalCoIF", "MaxCoIF", "PrimaryErrorCode"]
            ],
            use_container_width=True,
            hide_index=True,
        )

# ===========================================================================
# PAGE: Health Map
# ===========================================================================
elif page == "Health Map":
    page_header(
        "Integration Health Map",
        subtitle="Interfaces ranked by Total CoIF (business impact). Select a row to see the full CoIF breakdown.",
        icon="🗺️",
    )

    tabs = st.tabs(["By Interface", "By Business Process", "By System"])

    # --- Tab 1: Interface ---
    with tabs[0]:
        col_filter, col_table = st.columns([1, 3])
        with col_filter:
            priority_filter = st.multiselect(
                "Priority", options=sorted(iface_agg["Priority"].dropna().unique()),
                default=[]
            )
            area_filter = st.multiselect(
                "Area", options=sorted(iface_agg["Area"].dropna().unique()),
                default=[]
            )
            min_coif = st.number_input("Min Total CoIF", min_value=0.0, value=0.0, step=100.0)

        filtered = iface_agg.copy()
        if priority_filter:
            filtered = filtered[filtered["Priority"].isin(priority_filter)]
        if area_filter:
            filtered = filtered[filtered["Area"].isin(area_filter)]
        filtered = filtered[filtered["TotalCoIF"] >= min_coif]

        with col_table:
            display_cols = [
                "Rank", "InterfaceID", "SourceSystem", "TargetSystem",
                "BusinessProcess", "Priority", "PriorityWeight", "ProcessWeight",
                "FailureSignal", "CostMultiplier", "WindowType",
                "EventCount", "FailedCount", "SLA_Violations", "TotalCoIF",
            ]
            available_cols = [c for c in display_cols if c in filtered.columns]
            st.dataframe(
                filtered[available_cols].reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
            )

        # CoIF explanation panel
        st.markdown("### 📐 CoIF Explanation Panel")
        iface_list = filtered["InterfaceID"].tolist()
        if iface_list:
            selected_iface = st.selectbox("Select interface to explain:", iface_list)
            sel_row = filtered[filtered["InterfaceID"] == selected_iface].iloc[0]
            st.markdown(coif_explanation_card(sel_row), unsafe_allow_html=True)

            # Contributing events
            with st.expander(f"Events contributing to {selected_iface} CoIF", expanded=False):
                contrib = events[events["InterfaceID"] == selected_iface][
                    ["EventID", "Timestamp", "Status", "ErrorCode",
                     "RootCauseClass", "Latency_ms", "FailureSignal",
                     "PriorityWeight", "ProcessWeight", "CostMultiplier", "CoIF"]
                ]
                st.dataframe(contrib, use_container_width=True, hide_index=True)

    # --- Tab 2: Business Process ---
    with tabs[1]:
        # Sunburst: shows Process → Interface hierarchy in one view
        st.plotly_chart(
            coif_sunburst(events),
            use_container_width=True,
        )
        with st.expander("📋 Business Process CoIF Table", expanded=False):
            st.dataframe(
                proc_agg.reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
            )

    # --- Tab 3: System ---
    with tabs[2]:
        # Bubble chart: EventCount vs AvgLatency, sized by CoIF
        st.plotly_chart(
            coif_bubble_chart(sys_agg),
            use_container_width=True,
        )
        with st.expander("📋 System CoIF Table", expanded=False):
            st.dataframe(
                sys_agg.reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
            )

# ===========================================================================
# PAGE: Dependency Graph
# ===========================================================================
elif page == "Dependency Graph":
    page_header(
        "System Dependency Graph",
        subtitle="Directed graph of system integrations. Edge thickness and colour encode Total CoIF — thicker/redder = higher impact.",
        icon="🌐",
    )

    fig = graph_to_plotly(G)
    st.plotly_chart(fig, use_container_width=True)

    # Edge inspector
    st.markdown("### 🔍 Edge Inspector")
    edges = [(u, v) for u, v in G.edges()]
    if edges:
        edge_labels = [f"{u} → {v}" for u, v in edges]
        col1, col2 = st.columns([1, 2])
        with col1:
            sel_edge_label = st.selectbox("Select edge to inspect:", edge_labels)
            sel_src, sel_tgt = sel_edge_label.split(" → ")
            edge_data = get_edge_data(G, sel_src, sel_tgt)

        with col2:
            if edge_data:
                st.markdown(
                    f"""
                    <div style="background:#1e293b; border:1px solid #1e3a5f;
                                border-radius:12px; padding:20px;">
                        <h4 style="color:#38bdf8; margin:0 0 12px 0;">
                            {sel_src} → {sel_tgt}
                        </h4>
                        <table style="width:100%; border-collapse:collapse;">
                            <tr><td style="color:#94a3b8; padding:5px 0;">Event Count</td>
                                <td style="color:#e2e8f0; font-weight:600;">{edge_data.get('EventCount', 0):,}</td></tr>
                            <tr><td style="color:#94a3b8; padding:5px 0;">Failed Count</td>
                                <td style="color:#f87171; font-weight:600;">{edge_data.get('FailedCount', 0):,}</td></tr>
                            <tr><td style="color:#94a3b8; padding:5px 0;">Warning Count</td>
                                <td style="color:#fbbf24; font-weight:600;">{edge_data.get('WarningCount', 0):,}</td></tr>
                            <tr><td style="color:#94a3b8; padding:5px 0;">Total CoIF</td>
                                <td style="color:#a78bfa; font-weight:700; font-size:1.1rem;">
                                    {edge_data.get('TotalCoIF', 0):,.0f}</td></tr>
                            <tr><td style="color:#94a3b8; padding:5px 0;">Top Errors</td>
                                <td style="color:#e2e8f0;">{', '.join(str(e) for e in edge_data.get('TopErrorCodes', []))}</td></tr>
                            <tr><td style="color:#94a3b8; padding:5px 0;">Interfaces</td>
                                <td style="color:#e2e8f0;">{', '.join(str(i) for i in edge_data.get('AffectedInterfaces', []))}</td></tr>
                        </table>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Events on this edge
        with st.expander(f"Events on {sel_src} → {sel_tgt}", expanded=False):
            edge_events = events[
                (events["SourceSystem"] == sel_src) & (events["TargetSystem"] == sel_tgt)
            ]
            st.dataframe(
                edge_events[
                    ["EventID", "Timestamp", "InterfaceID", "Status",
                     "ErrorCode", "CoIF", "WindowType"]
                ],
                use_container_width=True,
                hide_index=True,
            )

# ===========================================================================
# PAGE: Incidents
# ===========================================================================
elif page == "Incidents":
    page_header(
        "Correlated Incidents",
        subtitle="Likely incident clusters ranked by Total CoIF. Correlated by RequestID, SessionID, temporal proximity, dependency chain, and error class.",
        icon="🚨",
    )

    if incidents_df.empty:
        st.info("No incidents detected.")
    else:
        # Summary table
        inc_display = incidents_df.copy()
        inc_display["AffectedSystems"] = inc_display["AffectedSystems"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else x
        )
        inc_display["AffectedInterfaces"] = inc_display["AffectedInterfaces"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else x
        )

        st.dataframe(
            inc_display[
                ["IncidentID", "StartTime", "EndTime", "EventCount",
                 "AffectedSystems", "AffectedInterfaces",
                 "PrimaryErrorCode", "PrimaryRootCauseClass",
                 "TotalCoIF", "MaxCoIF"]
            ],
            use_container_width=True,
            hide_index=True,
        )

        # Drill-down
        st.markdown("### 🔎 Incident Drill-Down")
        inc_id_list = inc_display["IncidentID"].tolist()
        sel_inc = st.selectbox("Select Incident:", inc_id_list)

        inc_row = incidents_df[incidents_df["IncidentID"] == sel_inc].iloc[0]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                f"""
                <div style="background:#1e293b; border:1px solid #1e3a5f;
                            border-radius:12px; padding:20px;">
                    <h4 style="color:#f87171; margin:0 0 12px 0;">🚨 {sel_inc}</h4>
                    <table style="width:100%; border-collapse:collapse;">
                        <tr><td style="color:#94a3b8; padding:5px 0;">Start Time</td>
                            <td style="color:#e2e8f0;">{inc_row['StartTime']}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">End Time</td>
                            <td style="color:#e2e8f0;">{inc_row['EndTime']}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Event Count</td>
                            <td style="color:#e2e8f0; font-weight:600;">{inc_row['EventCount']}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Total CoIF</td>
                            <td style="color:#f87171; font-weight:700; font-size:1.1rem;">
                                {inc_row['TotalCoIF']:,.0f}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Max Event CoIF</td>
                            <td style="color:#fbbf24; font-weight:600;">{inc_row['MaxCoIF']:,.0f}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Primary Error</td>
                            <td style="color:#e2e8f0;">{inc_row['PrimaryErrorCode']}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Root Cause</td>
                            <td style="color:#e2e8f0;">{inc_row['PrimaryRootCauseClass']}</td></tr>
                    </table>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            systems_html = " ".join(
                f'<span style="background:rgba(56,189,248,0.15); color:#38bdf8; '
                f'border:1px solid #38bdf8; padding:3px 10px; border-radius:20px; '
                f'margin:3px; display:inline-block; font-size:0.85rem;">{s}</span>'
                for s in inc_row["AffectedSystems"]
            )
            ifaces_html = " ".join(
                f'<span style="background:rgba(167,139,250,0.15); color:#a78bfa; '
                f'border:1px solid #a78bfa; padding:3px 10px; border-radius:20px; '
                f'margin:3px; display:inline-block; font-size:0.85rem;">{i}</span>'
                for i in inc_row["AffectedInterfaces"]
            )
            st.markdown(
                f"""
                <div style="background:#1e293b; border:1px solid #1e3a5f;
                            border-radius:12px; padding:20px; height:100%;">
                    <div style="color:#94a3b8; font-size:0.8rem; margin-bottom:6px;">
                        AFFECTED SYSTEMS
                    </div>
                    <div style="margin-bottom:14px;">{systems_html}</div>
                    <div style="color:#94a3b8; font-size:0.8rem; margin-bottom:6px;">
                        AFFECTED INTERFACES
                    </div>
                    <div>{ifaces_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Event timeline for selected incident
        inc_events = events[events.get("IncidentID", pd.Series(dtype=str)) == sel_inc] if "IncidentID" in events.columns else pd.DataFrame()
        if not inc_events.empty:
            st.markdown("#### Event Timeline")
            st.plotly_chart(event_timeline(inc_events), use_container_width=True)

            st.dataframe(
                inc_events[
                    ["EventID", "Timestamp", "InterfaceID", "SourceSystem",
                     "TargetSystem", "Status", "ErrorCode", "CoIF"]
                ].sort_values("Timestamp"),
                use_container_width=True,
                hide_index=True,
            )

# ===========================================================================
# PAGE: Event Explorer
# ===========================================================================
elif page == "Event Explorer":
    page_header(
        "Event Explorer",
        subtitle="Search, filter, and inspect all integration events. Select any event to see its full CoIF evidence trail.",
        icon="🔍",
    )

    # Filters
    with st.expander("🎛️ Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            f_source = st.multiselect("Source System", sorted(events["SourceSystem"].dropna().unique()))
            f_target = st.multiselect("Target System", sorted(events["TargetSystem"].dropna().unique()))
        with col2:
            f_iface = st.multiselect("Interface ID", sorted(events["InterfaceID"].dropna().unique()))
            f_process = st.multiselect("Business Process", sorted(events["BusinessProcess"].dropna().unique()))
        with col3:
            f_status = st.multiselect("Status", sorted(events["Status"].dropna().unique()))
            f_priority = st.multiselect("Priority", sorted(events["Priority"].dropna().unique()))
        with col4:
            f_error = st.multiselect("Error Code", sorted(events["ErrorCode"].dropna().unique()))
            f_window = st.multiselect("Window Type", sorted(events["WindowType"].dropna().unique()))

        col5, col6 = st.columns(2)
        with col5:
            min_ts = events["Timestamp"].min()
            max_ts = events["Timestamp"].max()
            ts_range = st.date_input(
                "Time Range",
                value=(min_ts.date(), max_ts.date()),
                min_value=min_ts.date(),
                max_value=max_ts.date(),
            )
        with col6:
            min_coif_filter = st.number_input("Min CoIF", min_value=0.0, value=0.0, step=100.0)

        text_search = st.text_input("🔎 Free text search (ErrorText / EventID / RootCauseClass):", "")

    # Apply filters
    filtered_events = events.copy()
    if f_source:
        filtered_events = filtered_events[filtered_events["SourceSystem"].isin(f_source)]
    if f_target:
        filtered_events = filtered_events[filtered_events["TargetSystem"].isin(f_target)]
    if f_iface:
        filtered_events = filtered_events[filtered_events["InterfaceID"].isin(f_iface)]
    if f_process:
        filtered_events = filtered_events[filtered_events["BusinessProcess"].isin(f_process)]
    if f_status:
        filtered_events = filtered_events[filtered_events["Status"].isin(f_status)]
    if f_priority:
        filtered_events = filtered_events[filtered_events["Priority"].isin(f_priority)]
    if f_error:
        filtered_events = filtered_events[filtered_events["ErrorCode"].isin(f_error)]
    if f_window:
        filtered_events = filtered_events[filtered_events["WindowType"].isin(f_window)]
    if len(ts_range) == 2:
        start_ts = pd.Timestamp(ts_range[0])
        end_ts = pd.Timestamp(ts_range[1]) + pd.Timedelta(days=1)
        filtered_events = filtered_events[
            (filtered_events["Timestamp"] >= start_ts)
            & (filtered_events["Timestamp"] < end_ts)
        ]
    filtered_events = filtered_events[filtered_events["CoIF"] >= min_coif_filter]
    if text_search:
        mask = (
            filtered_events["ErrorText"].astype(str).str.contains(text_search, case=False, na=False)
            | filtered_events["EventID"].astype(str).str.contains(text_search, case=False, na=False)
            | filtered_events.get("RootCauseClass", pd.Series("", index=filtered_events.index))
            .astype(str).str.contains(text_search, case=False, na=False)
        )
        filtered_events = filtered_events[mask]

    st.markdown(
        f"<div style='color:#94a3b8; margin-bottom:8px;'>Showing <b style='color:#38bdf8;'>"
        f"{len(filtered_events):,}</b> of {len(events):,} events</div>",
        unsafe_allow_html=True,
    )

    display_cols = [
        "EventID", "Timestamp", "InterfaceID", "SourceSystem", "TargetSystem",
        "BusinessProcess", "Status", "ErrorCode", "RootCauseClass",
        "Latency_ms", "WindowType", "CoIF",
    ]
    available = [c for c in display_cols if c in filtered_events.columns]
    st.dataframe(
        filtered_events[available].sort_values("CoIF", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    # Event detail panel
    st.markdown("### 📋 Event Detail")
    event_ids = filtered_events["EventID"].tolist()
    if event_ids:
        sel_event = st.selectbox("Select Event ID:", event_ids[:200])
        ev_row = filtered_events[filtered_events["EventID"] == sel_event].iloc[0]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                f"""
                <div style="background:#1e293b; border:1px solid #1e3a5f;
                            border-radius:12px; padding:20px;">
                    <h4 style="color:#38bdf8; margin:0 0 12px 0;">🎫 {sel_event}</h4>
                    <table style="width:100%; border-collapse:collapse;">
                        <tr><td style="color:#94a3b8; padding:5px 0;">Timestamp</td>
                            <td style="color:#e2e8f0;">{ev_row.get('Timestamp','')}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Interface</td>
                            <td style="color:#a78bfa;">{ev_row.get('InterfaceID','')}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Source → Target</td>
                            <td style="color:#e2e8f0;">{ev_row.get('SourceSystem','')} → {ev_row.get('TargetSystem','')}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Status</td>
                            <td style="color:{'#f87171' if ev_row.get('Status') == 'Failed' else '#fbbf24'};">
                                {ev_row.get('Status','')}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Error Code</td>
                            <td style="color:#e2e8f0;">{ev_row.get('ErrorCode','')}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Root Cause</td>
                            <td style="color:#e2e8f0;">{ev_row.get('RootCauseClass','')}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Error Text</td>
                            <td style="color:#e2e8f0; font-size:0.85rem;">{ev_row.get('ErrorText','')}</td></tr>
                        <tr><td style="color:#94a3b8; padding:5px 0;">Latency</td>
                            <td style="color:#e2e8f0;">{ev_row.get('Latency_ms','')} ms
                            {'⚠️ SLA violated' if ev_row.get('SLA_Violation') == 1 else '✅'}</td></tr>
                    </table>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(coif_explanation_card(ev_row), unsafe_allow_html=True)

    # Signature / dedup section
    st.markdown("### 🔏 Event Signatures (De-Duplication)")
    if "Signature" in filtered_events.columns:
        sig_summary = (
            filtered_events.groupby("Signature")
            .agg(
                DuplicateCount=("EventID", "count"),
                Status=("Status", "first"),
                ErrorCode=("ErrorCode", "first"),
                RootCauseClass=("RootCauseClass", "first"),
                NormErrorText=("NormErrorText", "first"),
                TotalCoIF=("CoIF", "sum"),
            )
            .sort_values("DuplicateCount", ascending=False)
            .reset_index()
        )
        st.dataframe(sig_summary.head(30), use_container_width=True, hide_index=True)

# ===========================================================================
# PAGE: Ask the Data
# ===========================================================================
elif page == "Ask the Data":
    page_header(
        "Ask the Data",
        subtitle="Evidence-grounded Q&A — all answers derived from the actual loaded dataset.",
        icon="💬",
    )

    # Example questions
    examples = [
        "Which interface has the highest CoIF?",
        "Top 5 incidents by business impact",
        "Which failures occurred during QEC?",
        "Which systems are most impacted?",
        "Which interface has the most SLA violations?",
        "Show me all failures affecting PAY",
        "Why is IF_PAY_001 high priority?",
        "Which failures occurred during MEC?",
    ]

    # Styled question chips
    st.markdown(
        "<div style='color:#8b92a5; font-size:0.75rem; text-transform:uppercase; "
        "letter-spacing:0.08em; margin-bottom:10px;'>Quick Questions</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    for i, ex in enumerate(examples):
        with cols[i % 4]:
            if st.button(ex, key=f"ex_{i}"):
                st.session_state["qa_input"] = ex

    # Styled search bar
    st.markdown(
        """
        <div style='margin:20px 0 8px 0; color:#8b92a5; font-size:0.8rem;
                    text-transform:uppercase; letter-spacing:0.08em;'>Your Question</div>
        """,
        unsafe_allow_html=True,
    )
    user_q = st.text_input(
        "Ask a question about the data:",
        value=st.session_state.get("qa_input", ""),
        placeholder="e.g. Which interface has the highest CoIF?",
        key="qa_input",
        label_visibility="collapsed",
    )

    if user_q.strip():
        with st.spinner("Querying dataset …"):
            answer = answer_question(
                user_q,
                df=events,
                interface_agg=iface_agg,
                system_agg=sys_agg,
                incidents_df=incidents_df,
            )

        st.markdown(
            f"""
            <div style="
                background: linear-gradient(145deg, #141728, #0d0f1a);
                border: 1px solid #1e2340;
                border-left: 3px solid #c9a84c;
                border-radius: 14px;
                padding: 22px 24px;
                margin: 16px 0;
            ">
                <div style="color:#c9a84c; font-size:0.7rem; text-transform:uppercase;
                            letter-spacing:0.1em; font-weight:600; margin-bottom:10px;">Answer</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(answer.answer)
        st.markdown("</div>", unsafe_allow_html=True)

        if not answer.evidence_df.empty:
            with st.expander(f"📎 {answer.evidence_label} ({len(answer.evidence_df)} rows)", expanded=True):
                display_ev_cols = [
                    "EventID", "Timestamp", "InterfaceID", "SourceSystem",
                    "TargetSystem", "BusinessProcess", "Status", "ErrorCode",
                    "FailureSignal", "PriorityWeight", "ProcessWeight",
                    "CostMultiplier", "CoIF",
                ]
                avail_ev = [c for c in display_ev_cols if c in answer.evidence_df.columns]
                st.dataframe(
                    answer.evidence_df[avail_ev],
                    use_container_width=True,
                    hide_index=True,
                )
