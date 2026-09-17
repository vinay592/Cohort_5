"""
ui_helpers.py
-------------
Streamlit / Plotly UI component helpers.
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Color palette & theme constants
# ---------------------------------------------------------------------------
DARK_BG = "#0f172a"
CARD_BG = "#1e293b"
ACCENT_BLUE = "#38bdf8"
ACCENT_PURPLE = "#a78bfa"
ACCENT_RED = "#f87171"
ACCENT_AMBER = "#fbbf24"
ACCENT_GREEN = "#34d399"
TEXT_MUTED = "#94a3b8"

PLOTLY_TEMPLATE = "plotly_dark"
PLOTLY_PAPER_BG = "#0f172a"
PLOTLY_PLOT_BG = "#1e293b"


def apply_dark_theme() -> None:
    """Inject CSS for the dark premium theme."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #1a2744 100%);
            border-right: 1px solid #1e3a5f;
        }

        /* Top header strip */
        [data-testid="stHeader"] {
            background: rgba(15,23,42,0.95);
            backdrop-filter: blur(10px);
        }

        /* Cards / metric containers */
        [data-testid="stMetric"] {
            background: #1e293b;
            border: 1px solid #1e3a5f;
            border-radius: 12px;
            padding: 16px !important;
        }

        [data-testid="stMetricLabel"] > div { color: #94a3b8 !important; font-size: 0.78rem !important; }
        [data-testid="stMetricValue"] > div { color: #38bdf8 !important; font-weight: 700; }

        /* Buttons */
        .stButton > button {
            background: linear-gradient(135deg, #1d4ed8, #7c3aed);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 20px rgba(56,189,248,0.3);
        }

        /* Dataframe */
        [data-testid="stDataFrame"] {
            border: 1px solid #1e3a5f;
            border-radius: 8px;
        }

        /* Tabs */
        [data-testid="stTabs"] button {
            color: #94a3b8;
            font-weight: 500;
        }
        [data-testid="stTabs"] button[aria-selected="true"] {
            color: #38bdf8;
            border-bottom: 2px solid #38bdf8;
        }

        /* Expander */
        [data-testid="stExpander"] > div {
            background: #1e293b;
            border: 1px solid #1e3a5f;
            border-radius: 8px;
        }

        /* Alert / info boxes */
        .stAlert { border-radius: 8px; }

        /* Text input */
        [data-testid="stTextInput"] input {
            background: #1e293b;
            border: 1px solid #1e3a5f;
            color: #e2e8f0;
            border-radius: 8px;
        }

        /* Select boxes */
        [data-testid="stSelectbox"] > div > div {
            background: #1e293b;
            border: 1px solid #1e3a5f;
            border-radius: 8px;
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

        /* CoIF badge */
        .coif-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.85rem;
        }
        .coif-critical { background: rgba(248,113,113,0.2); color: #f87171; border: 1px solid #f87171; }
        .coif-high     { background: rgba(251,191,36,0.2); color: #fbbf24; border: 1px solid #fbbf24; }
        .coif-medium   { background: rgba(56,189,248,0.2); color: #38bdf8; border: 1px solid #38bdf8; }
        .coif-low      { background: rgba(52,211,153,0.2); color: #34d399; border: 1px solid #34d399; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str | int | float, icon: str = "📊", delta: str | None = None) -> str:
    """Return HTML for a single KPI metric card."""
    val_str = f"{value:,.0f}" if isinstance(value, (int, float)) else str(value)
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta else ""
    return f"""
    <div style="
        background: linear-gradient(135deg, #1e293b, #0f2640);
        border: 1px solid #1e3a5f;
        border-radius: 12px;
        padding: 18px 22px;
        text-align: center;
        min-height: 100px;
    ">
        <div style="font-size:1.8rem; margin-bottom:4px;">{icon}</div>
        <div style="font-size:0.75rem; color:#94a3b8; text-transform:uppercase;
                    letter-spacing:0.08em; margin-bottom:6px;">{label}</div>
        <div style="font-size:1.7rem; font-weight:700; color:#38bdf8; line-height:1.1;">{val_str}</div>
        {delta_html}
    </div>
    """


def coif_bar_chart(agg_df: pd.DataFrame, x_col: str, title: str) -> go.Figure:
    """Horizontal bar chart of CoIF values."""
    df = agg_df.nlargest(15, "TotalCoIF").sort_values("TotalCoIF")
    fig = px.bar(
        df,
        x="TotalCoIF",
        y=x_col,
        orientation="h",
        title=title,
        color="TotalCoIF",
        color_continuous_scale=["#1d4ed8", "#7c3aed", "#f87171"],
        labels={"TotalCoIF": "Total CoIF", x_col: ""},
        template=PLOTLY_TEMPLATE,
    )
    fig.update_layout(
        paper_bgcolor=PLOTLY_PAPER_BG,
        plot_bgcolor=PLOTLY_PLOT_BG,
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=40, b=10),
        font=dict(family="Inter", color="#e2e8f0"),
        title_font=dict(size=14),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#1e3a5f", tickformat=",.0f")
    fig.update_yaxes(showgrid=False)
    return fig


def coif_treemap(agg_df: pd.DataFrame, path_col: str, title: str) -> go.Figure:
    """Treemap of CoIF by the given path column."""
    fig = px.treemap(
        agg_df,
        path=[path_col],
        values="TotalCoIF",
        color="TotalCoIF",
        color_continuous_scale=["#1d4ed8", "#7c3aed", "#f87171"],
        title=title,
        template=PLOTLY_TEMPLATE,
    )
    fig.update_layout(
        paper_bgcolor=PLOTLY_PAPER_BG,
        margin=dict(l=0, r=0, t=40, b=0),
        font=dict(family="Inter", color="#e2e8f0"),
    )
    return fig


def event_timeline(df: pd.DataFrame) -> go.Figure:
    """Scatter plot of events over time, coloured by Status."""
    colors = {"Failed": ACCENT_RED, "Warning": ACCENT_AMBER}
    fig = px.scatter(
        df,
        x="Timestamp",
        y="CoIF",
        color="Status",
        color_discrete_map=colors,
        hover_data=["EventID", "InterfaceID", "ErrorCode", "WindowType"],
        template=PLOTLY_TEMPLATE,
        title="Event Timeline – CoIF over Time",
    )
    fig.update_layout(
        paper_bgcolor=PLOTLY_PAPER_BG,
        plot_bgcolor=PLOTLY_PLOT_BG,
        margin=dict(l=10, r=10, t=40, b=10),
        font=dict(family="Inter", color="#e2e8f0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#1e3a5f")
    fig.update_yaxes(showgrid=True, gridcolor="#1e3a5f", tickformat=",.0f")
    return fig


def coif_explanation_card(row: pd.Series) -> str:
    """Return HTML for the CoIF breakdown of a single interface row."""
    fs = row.get("FailureSignal", "?")
    pw = row.get("PriorityWeight", "?")
    piw = row.get("ProcessWeight", "?")
    cm = row.get("CostMultiplier", "?")
    coif = row.get("TotalCoIF", "?")
    iface = row.get("InterfaceID", "?")
    proc = row.get("BusinessProcess", "?")
    priority = row.get("Priority", "?")
    wtype = row.get("WindowType", "?")

    try:
        single_coif = float(fs) * float(pw) * float(piw) * float(cm)
        formula = f"{fs} × {pw} × {piw} × {cm} = {single_coif:,.0f}"
    except (ValueError, TypeError):
        formula = f"{fs} × {pw} × {piw} × {cm} = ?"

    return f"""
    <div style="
        background: linear-gradient(135deg, #0f2640, #1e293b);
        border: 1px solid #1e3a5f;
        border-radius: 14px;
        padding: 24px;
        font-family: 'Inter', sans-serif;
    ">
        <h3 style="color:#38bdf8; margin: 0 0 16px 0;">📐 CoIF Breakdown: {iface}</h3>
        <table style="width:100%; border-collapse:collapse;">
            <tr><td style="color:#94a3b8; padding:6px 0;">Business Process</td>
                <td style="color:#e2e8f0; font-weight:500;">{proc}</td></tr>
            <tr><td style="color:#94a3b8; padding:6px 0;">Priority</td>
                <td style="color:#e2e8f0; font-weight:500;">{priority}</td></tr>
            <tr><td style="color:#94a3b8; padding:6px 0;">Failure Signal</td>
                <td style="color:#fbbf24; font-weight:600;">{fs}</td></tr>
            <tr><td style="color:#94a3b8; padding:6px 0;">Priority Weight</td>
                <td style="color:#a78bfa; font-weight:600;">{pw}</td></tr>
            <tr><td style="color:#94a3b8; padding:6px 0;">Process Weight</td>
                <td style="color:#a78bfa; font-weight:600;">{piw}</td></tr>
            <tr><td style="color:#94a3b8; padding:6px 0;">Calendar Window</td>
                <td style="color:#38bdf8; font-weight:500;">{wtype}</td></tr>
            <tr><td style="color:#94a3b8; padding:6px 0;">Cost Multiplier</td>
                <td style="color:#f87171; font-weight:600;">{cm}</td></tr>
        </table>
        <div style="
            margin-top: 20px;
            border-top: 1px solid #1e3a5f;
            padding-top: 16px;
            font-family: 'Space Mono', monospace;
            font-size: 0.95rem;
        ">
            <div style="color:#94a3b8; margin-bottom:6px;">Single Event CoIF Formula (Example)</div>
            <div style="color:#e2e8f0; font-size:1.1rem; margin-bottom:12px;">{formula}</div>
            
            <div style="color:#94a3b8; margin-bottom:6px;">Total CoIF (Sum across all {row.get('EventCount', '?')} events)</div>
            <div style="color:#f87171; font-size:1.4rem; font-weight:700;">{coif:,.0f}</div>
        </div>
    </div>
    """


def priority_badge(priority: str) -> str:
    """Return a coloured HTML badge for a priority level."""
    colors = {
        "Critical": ("#f87171", "rgba(248,113,113,0.15)"),
        "High":     ("#fbbf24", "rgba(251,191,36,0.15)"),
        "Elevated": ("#38bdf8", "rgba(56,189,248,0.15)"),
        "Normal":   ("#34d399", "rgba(52,211,153,0.15)"),
        "Low":      ("#94a3b8", "rgba(148,163,184,0.15)"),
    }
    fg, bg = colors.get(priority, ("#e2e8f0", "rgba(226,232,240,0.15)"))
    return (
        f'<span style="background:{bg}; color:{fg}; border:1px solid {fg}; '
        f'padding:2px 10px; border-radius:12px; font-size:0.78rem; '
        f'font-weight:600;">{priority}</span>'
    )
