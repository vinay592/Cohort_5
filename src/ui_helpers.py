"""
ui_helpers.py
-------------
Streamlit / Plotly UI component helpers — Executive-class redesign.

Color Language:
    Executive Gold  #c9a84c / #f0c060  — primary accent, value numbers
    Deep Indigo     #6366f1             — secondary accent, links
    Alert Red       #ef4444
    Alert Amber     #f59e0b
    Success Green   #10b981
    Charcoal BG     #0d0f1a / #141728
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Color palette & theme constants
# ---------------------------------------------------------------------------
DARK_BG       = "#0d0f1a"    # Near-black deep navy
CARD_BG       = "#141728"    # Deep indigo card
CARD_BG2      = "#1a1e35"    # Slightly lighter card variant
ACCENT_GOLD   = "#c9a84c"    # Executive gold — the primary accent
ACCENT_GOLD2  = "#f0c060"    # Light gold for highlights
ACCENT_INDIGO = "#6366f1"    # Indigo-500
ACCENT_RED    = "#ef4444"    # Failure red
ACCENT_AMBER  = "#f59e0b"    # Warning amber
ACCENT_GREEN  = "#10b981"    # Success green
TEXT_PRIMARY  = "#e8eaf0"    # Near-white text
TEXT_MUTED    = "#8b92a5"    # Muted label text
BORDER_COLOR  = "#1e2340"    # Subtle border
GLOW_GOLD     = "rgba(201,168,76,0.18)"
GLOW_INDIGO   = "rgba(99,102,241,0.18)"

PLOTLY_TEMPLATE   = "plotly_dark"
PLOTLY_PAPER_BG   = DARK_BG
PLOTLY_PLOT_BG    = CARD_BG
PLOTLY_GRID_COLOR = "#1e2340"
PLOTLY_FONT       = dict(family="'Inter', sans-serif", color=TEXT_PRIMARY, size=12)


# ---------------------------------------------------------------------------
# Theme injection
# ---------------------------------------------------------------------------

def apply_dark_theme() -> None:
    """Inject CSS for the executive dark theme with glassmorphism."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600;700&display=swap');

        /* ── Root resets ──────────────────────────────────────────────── */
        html, body, [class*="css"] {
            font-family: 'DM Sans', 'Inter', sans-serif;
            background-color: #0d0f1a;
            color: #e8eaf0;
        }

        /* ── Main content area ────────────────────────────────────────── */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1400px;
        }

        /* ── Sidebar ──────────────────────────────────────────────────── */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0a0c18 0%, #0f1228 60%, #141728 100%);
            border-right: 1px solid #1e2340;
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 0.5rem;
        }

        /* sidebar radio — styled nav pills */
        [data-testid="stSidebar"] [data-testid="stRadio"] > div {
            gap: 2px;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label {
            display: flex;
            align-items: center;
            padding: 9px 14px;
            border-radius: 8px;
            cursor: pointer;
            color: #8b92a5;
            font-weight: 500;
            font-size: 0.88rem;
            transition: all 0.18s ease;
            border: 1px solid transparent;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
            background: rgba(201,168,76,0.08);
            color: #c9a84c;
            border-color: rgba(201,168,76,0.2);
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] div:first-child {
            display: none;  /* hide the default radio dot */
        }

        /* ── Top header strip ─────────────────────────────────────────── */
        [data-testid="stHeader"] {
            background: rgba(13,15,26,0.96);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid #1e2340;
        }

        /* ── KPI Metric widget ────────────────────────────────────────── */
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, #141728, #0d0f1a);
            border: 1px solid #1e2340;
            border-radius: 14px;
            padding: 18px !important;
        }
        [data-testid="stMetricLabel"] > div {
            color: #8b92a5 !important;
            font-size: 0.75rem !important;
            text-transform: uppercase;
            letter-spacing: 0.07em;
        }
        [data-testid="stMetricValue"] > div { color: #c9a84c !important; font-weight: 700; }

        /* ── Buttons ──────────────────────────────────────────────────── */
        .stButton > button {
            background: linear-gradient(135deg, rgba(99,102,241,0.25), rgba(201,168,76,0.15));
            color: #c9a84c;
            border: 1px solid rgba(201,168,76,0.35);
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.83rem;
            transition: all 0.2s ease;
            padding: 7px 14px;
        }
        .stButton > button:hover {
            background: linear-gradient(135deg, rgba(201,168,76,0.22), rgba(99,102,241,0.22));
            border-color: #c9a84c;
            transform: translateY(-1px);
            box-shadow: 0 4px 20px rgba(201,168,76,0.2);
            color: #f0c060;
        }

        /* ── Dataframe ────────────────────────────────────────────────── */
        [data-testid="stDataFrame"] {
            border: 1px solid #1e2340;
            border-radius: 10px;
            overflow: hidden;
        }

        /* ── Tabs ─────────────────────────────────────────────────────── */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            background: #141728;
            border-bottom: 1px solid #1e2340;
            border-radius: 10px 10px 0 0;
            padding: 4px 8px 0 8px;
            gap: 4px;
        }
        [data-testid="stTabs"] button {
            color: #8b92a5;
            font-weight: 500;
            font-size: 0.875rem;
            border-radius: 8px 8px 0 0;
            padding: 8px 18px;
            transition: all 0.15s;
        }
        [data-testid="stTabs"] button:hover { color: #c9a84c; }
        [data-testid="stTabs"] button[aria-selected="true"] {
            color: #c9a84c;
            background: rgba(201,168,76,0.08);
            border-bottom: 2px solid #c9a84c;
        }

        /* ── Expander ─────────────────────────────────────────────────── */
        [data-testid="stExpander"] > div {
            background: #141728;
            border: 1px solid #1e2340;
            border-radius: 10px;
        }
        [data-testid="stExpander"] summary {
            color: #c9a84c;
            font-weight: 500;
        }

        /* ── Alerts ───────────────────────────────────────────────────── */
        .stAlert { border-radius: 10px; }

        /* ── Text input ───────────────────────────────────────────────── */
        [data-testid="stTextInput"] input {
            background: #141728;
            border: 1px solid #1e2340;
            color: #e8eaf0;
            border-radius: 10px;
            font-size: 0.9rem;
            transition: border-color 0.2s;
        }
        [data-testid="stTextInput"] input:focus {
            border-color: #c9a84c;
            box-shadow: 0 0 0 2px rgba(201,168,76,0.12);
        }

        /* ── Selectbox ────────────────────────────────────────────────── */
        [data-testid="stSelectbox"] > div > div {
            background: #141728;
            border: 1px solid #1e2340;
            border-radius: 10px;
        }

        /* ── Multiselect ──────────────────────────────────────────────── */
        [data-testid="stMultiSelect"] > div > div {
            background: #141728;
            border: 1px solid #1e2340;
            border-radius: 10px;
        }

        /* ── Number input ─────────────────────────────────────────────── */
        [data-testid="stNumberInput"] input {
            background: #141728;
            border: 1px solid #1e2340;
            color: #e8eaf0;
            border-radius: 10px;
        }

        /* ── Scrollbar ────────────────────────────────────────────────── */
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: #0d0f1a; }
        ::-webkit-scrollbar-thumb { background: #2a2f4a; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #c9a84c; }

        /* ── Severity badges ──────────────────────────────────────────── */
        .badge-critical { background: rgba(239,68,68,0.15);  color: #ef4444; border: 1px solid rgba(239,68,68,0.4);  padding:2px 10px; border-radius:12px; font-size:0.78rem; font-weight:600; }
        .badge-high     { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.4); padding:2px 10px; border-radius:12px; font-size:0.78rem; font-weight:600; }
        .badge-elevated { background: rgba(201,168,76,0.15); color: #c9a84c; border: 1px solid rgba(201,168,76,0.4); padding:2px 10px; border-radius:12px; font-size:0.78rem; font-weight:600; }
        .badge-normal   { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.4); padding:2px 10px; border-radius:12px; font-size:0.78rem; font-weight:600; }
        .badge-low      { background: rgba(139,146,165,0.15);color: #8b92a5; border: 1px solid rgba(139,146,165,0.4);padding:2px 10px; border-radius:12px; font-size:0.78rem; font-weight:600; }

        /* ── Divider line ─────────────────────────────────────────────── */
        .gold-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent, #c9a84c, transparent);
            margin: 24px 0;
            opacity: 0.4;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Page header component
# ---------------------------------------------------------------------------

def page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """Render an executive-styled page header with a gold accent underline."""
    icon_html = f'<span style="font-size:1.6rem; margin-right:10px;">{icon}</span>' if icon else ""
    subtitle_html = (
        f'<div style="color:{TEXT_MUTED}; font-size:0.9rem; margin-top:4px; font-weight:400;">{subtitle}</div>'
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div style="margin-bottom: 28px;">
            <div style="display:flex; align-items:center; margin-bottom:6px;">
                {icon_html}
                <h1 style="
                    margin:0;
                    font-size:1.65rem;
                    font-weight:700;
                    color:{TEXT_PRIMARY};
                    letter-spacing:-0.01em;
                    font-family:'DM Sans', sans-serif;
                ">{title}</h1>
            </div>
            {subtitle_html}
            <div style="
                height:2px;
                width:60px;
                background:linear-gradient(90deg, {ACCENT_GOLD}, {ACCENT_INDIGO});
                border-radius:2px;
                margin-top:10px;
            "></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# KPI Card
# ---------------------------------------------------------------------------

_KPI_COLOR_MAP = {
    # label keyword → (value color, glow rgba)
    "failed":    (ACCENT_RED,    "rgba(239,68,68,0.12)"),
    "warning":   (ACCENT_AMBER,  "rgba(245,158,11,0.12)"),
    "sla":       (ACCENT_AMBER,  "rgba(245,158,11,0.12)"),
    "incident":  (ACCENT_RED,    "rgba(239,68,68,0.12)"),
    "coif":      (ACCENT_GOLD2,  "rgba(201,168,76,0.12)"),
    "interface": (ACCENT_INDIGO, "rgba(99,102,241,0.12)"),
    "system":    (ACCENT_INDIGO, "rgba(99,102,241,0.12)"),
}

def _kpi_colors(label: str):
    key = label.lower()
    for kw, colors in _KPI_COLOR_MAP.items():
        if kw in key:
            return colors
    return (ACCENT_GOLD, GLOW_GOLD)


def kpi_card(label: str, value: str | int | float, icon: str = "📊", delta: str | None = None) -> str:
    """Return HTML for a single color-coded KPI metric card."""
    val_str = f"{value:,.0f}" if isinstance(value, (int, float)) else str(value)
    val_color, glow = _kpi_colors(label)
    delta_html = (
        f'<div style="font-size:0.72rem; color:{TEXT_MUTED}; margin-top:4px;">{delta}</div>'
        if delta else ""
    )
    return f"""
    <div style="
        background: linear-gradient(145deg, {CARD_BG}, #0d0f1a);
        border: 1px solid {BORDER_COLOR};
        border-top: 2px solid {val_color};
        border-radius: 14px;
        padding: 18px 20px;
        text-align: left;
        min-height: 108px;
        box-shadow: 0 4px 24px {glow};
        position: relative;
        overflow: hidden;
        transition: box-shadow 0.2s;
    ">
        <div style="
            position:absolute; top:0; right:0;
            width:60px; height:60px;
            background: radial-gradient(circle at top right, {glow}, transparent 70%);
        "></div>
        <div style="font-size:1.35rem; margin-bottom:6px; opacity:0.85;">{icon}</div>
        <div style="
            font-size:0.7rem;
            color:{TEXT_MUTED};
            text-transform:uppercase;
            letter-spacing:0.09em;
            font-weight:500;
            margin-bottom:6px;
        ">{label}</div>
        <div style="
            font-size:1.75rem;
            font-weight:800;
            color:{val_color};
            line-height:1.1;
            font-family:'DM Sans', sans-serif;
        ">{val_str}</div>
        {delta_html}
    </div>
    """


# ---------------------------------------------------------------------------
# Bar chart (kept for Interface ranking — the primary operational chart)
# ---------------------------------------------------------------------------

def coif_bar_chart(agg_df: pd.DataFrame, x_col: str, title: str) -> go.Figure:
    """Horizontal bar chart of CoIF values — executive gold-to-red gradient."""
    df = agg_df.nlargest(15, "TotalCoIF").sort_values("TotalCoIF")
    fig = px.bar(
        df,
        x="TotalCoIF",
        y=x_col,
        orientation="h",
        title=title,
        color="TotalCoIF",
        color_continuous_scale=[ACCENT_GOLD, "#e07b39", ACCENT_RED],
        labels={"TotalCoIF": "Total CoIF", x_col: ""},
        template=PLOTLY_TEMPLATE,
    )
    fig.update_layout(
        paper_bgcolor=PLOTLY_PAPER_BG,
        plot_bgcolor=PLOTLY_PLOT_BG,
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=44, b=10),
        font=PLOTLY_FONT,
        title_font=dict(size=14, color=ACCENT_GOLD, family="DM Sans"),
        title_x=0.0,
        bargap=0.35,
    )
    fig.update_xaxes(
        showgrid=True, gridcolor=PLOTLY_GRID_COLOR,
        tickformat=",.0f", tickfont=dict(size=11),
        zeroline=False,
    )
    fig.update_yaxes(showgrid=False, tickfont=dict(size=11))
    fig.update_traces(
        marker_line_width=0,
        hovertemplate="<b>%{y}</b><br>CoIF: %{x:,.0f}<extra></extra>",
    )
    return fig


# ---------------------------------------------------------------------------
# Treemap
# ---------------------------------------------------------------------------

def coif_treemap(agg_df: pd.DataFrame, path_col: str, title: str) -> go.Figure:
    """Treemap of CoIF by the given path column — executive palette."""
    fig = px.treemap(
        agg_df,
        path=[path_col],
        values="TotalCoIF",
        color="TotalCoIF",
        color_continuous_scale=[ACCENT_INDIGO, ACCENT_GOLD, ACCENT_RED],
        title=title,
        template=PLOTLY_TEMPLATE,
    )
    fig.update_layout(
        paper_bgcolor=PLOTLY_PAPER_BG,
        margin=dict(l=0, r=0, t=44, b=0),
        font=PLOTLY_FONT,
        title_font=dict(size=14, color=ACCENT_GOLD, family="DM Sans"),
        title_x=0.0,
    )
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>CoIF: %{value:,.0f}<extra></extra>",
        textfont_size=12,
        root_color=DARK_BG,
    )
    return fig


# ---------------------------------------------------------------------------
# Event Timeline — area + scatter combo
# ---------------------------------------------------------------------------

def event_timeline(df: pd.DataFrame) -> go.Figure:
    """Upgraded timeline: filled area showing CoIF density + colored scatter."""
    fig = go.Figure()

    status_colors = {
        "Failed":  ACCENT_RED,
        "Warning": ACCENT_AMBER,
    }

    # Subtle area for overall CoIF volume
    df_sorted = df.sort_values("Timestamp")
    fig.add_trace(
        go.Scatter(
            x=df_sorted["Timestamp"],
            y=df_sorted["CoIF"],
            mode="lines",
            line=dict(color=ACCENT_GOLD, width=0.5),
            fill="tozeroy",
            fillcolor=f"rgba(201,168,76,0.07)",
            name="CoIF Area",
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Scatter points per status
    for status, color in status_colors.items():
        subset = df[df["Status"] == status]
        if subset.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=subset["Timestamp"],
                y=subset["CoIF"],
                mode="markers",
                name=status,
                marker=dict(
                    color=color,
                    size=5,
                    opacity=0.75,
                    line=dict(width=0),
                ),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Interface: %{customdata[1]}<br>"
                    "Error: %{customdata[2]}<br>"
                    "CoIF: %{y:,.0f}<br>"
                    "Time: %{x}<extra></extra>"
                ),
                customdata=subset[["EventID", "InterfaceID", "ErrorCode"]].values,
            )
        )

    fig.update_layout(
        title="Event Timeline — CoIF over Time",
        title_font=dict(size=14, color=ACCENT_GOLD, family="DM Sans"),
        paper_bgcolor=PLOTLY_PAPER_BG,
        plot_bgcolor=PLOTLY_PLOT_BG,
        margin=dict(l=10, r=10, t=44, b=10),
        font=PLOTLY_FONT,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            bgcolor="rgba(0,0,0,0)", font=dict(size=11),
        ),
        hovermode="closest",
    )
    fig.update_xaxes(showgrid=True, gridcolor=PLOTLY_GRID_COLOR, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=PLOTLY_GRID_COLOR, tickformat=",.0f", zeroline=False)
    return fig


# ---------------------------------------------------------------------------
# NEW: Status Donut Chart
# ---------------------------------------------------------------------------

def coif_donut_chart(events_df: pd.DataFrame) -> go.Figure:
    """
    Donut chart showing the Failed / Warning / Success event distribution.
    Replaces the redundant Business Process bar chart on the Overview page.
    """
    status_counts = events_df["Status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]

    color_map = {
        "Failed":  ACCENT_RED,
        "Warning": ACCENT_AMBER,
        "Success": ACCENT_GREEN,
        "Retry":   ACCENT_INDIGO,
    }
    colors = [color_map.get(s, ACCENT_GOLD) for s in status_counts["Status"]]

    total = status_counts["Count"].sum()

    fig = go.Figure(
        go.Pie(
            labels=status_counts["Status"],
            values=status_counts["Count"],
            hole=0.62,
            marker=dict(
                colors=colors,
                line=dict(color=DARK_BG, width=3),
            ),
            textinfo="label+percent",
            textfont=dict(size=12, family="DM Sans"),
            hovertemplate="<b>%{label}</b><br>Events: %{value:,}<br>Share: %{percent}<extra></extra>",
            direction="clockwise",
            sort=False,
        )
    )

    fig.update_layout(
        title="Event Status Distribution",
        title_font=dict(size=14, color=ACCENT_GOLD, family="DM Sans"),
        paper_bgcolor=PLOTLY_PAPER_BG,
        margin=dict(l=10, r=10, t=44, b=10),
        font=PLOTLY_FONT,
        legend=dict(
            orientation="v",
            yanchor="middle", y=0.5,
            xanchor="right", x=1.15,
            font=dict(size=11),
        ),
        annotations=[
            dict(
                text=f"<b>{total:,}</b><br><span style='font-size:10px'>Total</span>",
                x=0.5, y=0.5,
                font=dict(size=16, color=TEXT_PRIMARY, family="DM Sans"),
                showarrow=False,
            )
        ],
    )
    return fig


# ---------------------------------------------------------------------------
# NEW: Sunburst chart — Business Process → Interface hierarchy
# ---------------------------------------------------------------------------

def coif_sunburst(events_df: pd.DataFrame) -> go.Figure:
    """
    Sunburst chart: Business Process (inner ring) → Interface (outer ring),
    sized and colored by TotalCoIF. Replaces the flat Business Process bar chart.
    """
    agg = (
        events_df.groupby(["BusinessProcess", "InterfaceID"])
        .agg(TotalCoIF=("CoIF", "sum"))
        .reset_index()
    )

    fig = px.sunburst(
        agg,
        path=["BusinessProcess", "InterfaceID"],
        values="TotalCoIF",
        color="TotalCoIF",
        color_continuous_scale=[ACCENT_INDIGO, ACCENT_GOLD, ACCENT_RED],
        title="CoIF by Business Process → Interface",
        template=PLOTLY_TEMPLATE,
    )
    fig.update_layout(
        paper_bgcolor=PLOTLY_PAPER_BG,
        margin=dict(l=0, r=0, t=50, b=0),
        font=PLOTLY_FONT,
        title_font=dict(size=14, color=ACCENT_GOLD, family="DM Sans"),
        title_x=0.0,
        coloraxis_showscale=False,
    )
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>CoIF: %{value:,.0f}<extra></extra>",
        textfont=dict(size=11),
        insidetextorientation="radial",
    )
    return fig


# ---------------------------------------------------------------------------
# NEW: Bubble chart — System EventCount vs AvgLatency vs TotalCoIF
# ---------------------------------------------------------------------------

def coif_bubble_chart(sys_agg: pd.DataFrame) -> go.Figure:
    """
    Bubble chart: X = EventCount, Y = AvgLatency_ms, bubble size = TotalCoIF.
    Color encodes TotalCoIF. Replaces the flat System bar chart.
    Each bubble is a system — gives a richer 3-dimensional view.
    """
    df = sys_agg.copy()
    # Normalise bubble size for visual clarity
    max_coif = df["TotalCoIF"].max() if df["TotalCoIF"].max() > 0 else 1
    df["BubbleSize"] = (df["TotalCoIF"] / max_coif * 55 + 8).round(1)

    fig = go.Figure()

    for _, row in df.iterrows():
        coif_norm = row["TotalCoIF"] / max_coif
        # interpolate gold(low) → red(high)
        r = int(201 + (239 - 201) * coif_norm)
        g = int(168 * (1 - coif_norm) + 68 * coif_norm)
        b = int(76 * (1 - coif_norm) + 68 * coif_norm)
        color = f"rgba({r},{g},{b},0.82)"

        fig.add_trace(
            go.Scatter(
                x=[row["EventCount"]],
                y=[row.get("AvgLatency_ms", 0)],
                mode="markers+text",
                text=[row["System"]],
                textposition="top center",
                textfont=dict(size=10, color=TEXT_MUTED),
                marker=dict(
                    size=row["BubbleSize"],
                    color=color,
                    line=dict(width=1.5, color="rgba(255,255,255,0.15)"),
                    sizemode="diameter",
                ),
                name=row["System"],
                hovertemplate=(
                    f"<b>{row['System']}</b><br>"
                    f"Events: {row['EventCount']:,}<br>"
                    f"Avg Latency: {row.get('AvgLatency_ms', 0):,.0f} ms<br>"
                    f"Total CoIF: {row['TotalCoIF']:,.0f}<br>"
                    f"Failed: {row['FailedCount']:,}<extra></extra>"
                ),
                showlegend=False,
            )
        )

    fig.update_layout(
        title="System Risk Profile — Volume vs Latency (bubble = CoIF)",
        title_font=dict(size=14, color=ACCENT_GOLD, family="DM Sans"),
        paper_bgcolor=PLOTLY_PAPER_BG,
        plot_bgcolor=PLOTLY_PLOT_BG,
        margin=dict(l=10, r=10, t=50, b=40),
        font=PLOTLY_FONT,
        xaxis=dict(
            title="Event Count",
            showgrid=True, gridcolor=PLOTLY_GRID_COLOR,
            zeroline=False, tickformat=",",
        ),
        yaxis=dict(
            title="Avg Latency (ms)",
            showgrid=True, gridcolor=PLOTLY_GRID_COLOR,
            zeroline=False, tickformat=",",
        ),
        hovermode="closest",
    )
    return fig


# ---------------------------------------------------------------------------
# CoIF explanation card
# ---------------------------------------------------------------------------

def coif_explanation_card(row: pd.Series) -> str:
    """Return HTML for the CoIF breakdown of a single interface row."""
    fs  = row.get("FailureSignal", "?")
    pw  = row.get("PriorityWeight", "?")
    piw = row.get("ProcessWeight", "?")
    cm  = row.get("CostMultiplier", "?")
    coif = row.get("TotalCoIF", "?")
    iface   = row.get("InterfaceID", "?")
    proc    = row.get("BusinessProcess", "?")
    priority = row.get("Priority", "?")
    wtype   = row.get("WindowType", "?")

    try:
        structural = (float(pw) * 0.6) + (float(piw) * 0.4)
        cost_fac = 1.0 + (float(cm) - 1.0) * 0.25
        base_score = structural * float(fs) * cost_fac
        
        # Use simple heuristic to display the right explanation based on which model is active
        if abs(float(coif) - min(base_score, 100.0)) < 0.1:
            formula = f"Enhanced Baseline: (Struct={structural:.0f} × Freq={fs} × Cost={cost_fac:.2f}) = {base_score:.0f} (capped at 100)"
        else:
            formula = f"ML Model (Features: Priority={pw}, Process={piw}, Freq={fs}, Cal={cm})"
    except (ValueError, TypeError):
        formula = f"ML Model Prediction / Legacy Error"

    try:
        coif_fmt = f"{float(coif):,.0f}"
    except (ValueError, TypeError):
        coif_fmt = str(coif)

    def row_html(label, val, color=TEXT_PRIMARY):
        return (
            f'<tr>'
            f'<td style="color:{TEXT_MUTED}; padding:7px 0; font-size:0.82rem; '
            f'text-transform:uppercase; letter-spacing:0.06em; width:45%;">{label}</td>'
            f'<td style="color:{color}; font-weight:600; font-size:0.9rem;">{val}</td>'
            f'</tr>'
        )

    return f"""
    <div style="
        background: linear-gradient(145deg, {CARD_BG}, #0d0f1a);
        border: 1px solid {BORDER_COLOR};
        border-left: 3px solid {ACCENT_GOLD};
        border-radius: 14px;
        padding: 24px;
        font-family: 'DM Sans', sans-serif;
    ">
        <div style="color:{ACCENT_GOLD}; font-size:0.7rem; text-transform:uppercase;
                    letter-spacing:0.1em; margin-bottom:4px;">CoIF Breakdown</div>
        <div style="color:{TEXT_PRIMARY}; font-size:1.05rem; font-weight:700;
                    margin-bottom:18px;">{iface}</div>
        <table style="width:100%; border-collapse:collapse;">
            {row_html("Business Process", proc)}
            {row_html("Priority", priority, ACCENT_AMBER)}
            {row_html("Failure Signal", fs, ACCENT_AMBER)}
            {row_html("Priority Weight", pw, ACCENT_INDIGO)}
            {row_html("Process Weight", piw, ACCENT_INDIGO)}
            {row_html("Calendar Window", wtype)}
            {row_html("Cost Multiplier", cm, ACCENT_RED)}
        </table>
        <div style="
            margin-top:20px;
            border-top:1px solid {BORDER_COLOR};
            padding-top:16px;
        ">
            <div style="color:{TEXT_MUTED}; font-size:0.72rem; text-transform:uppercase;
                        letter-spacing:0.08em; margin-bottom:6px;">Single Event Formula</div>
            <div style="
                font-family:'Space Mono', monospace;
                font-size:0.9rem;
                color:{TEXT_PRIMARY};
                background:rgba(201,168,76,0.06);
                padding:10px 14px;
                border-radius:8px;
                margin-bottom:16px;
            ">{formula}</div>
            <div style="color:{TEXT_MUTED}; font-size:0.72rem; text-transform:uppercase;
                        letter-spacing:0.08em; margin-bottom:6px;">
                Total CoIF ({row.get("EventCount", "?")!s} events)
            </div>
            <div style="font-size:2rem; font-weight:800; color:{ACCENT_GOLD};
                        font-family:'DM Sans', sans-serif; letter-spacing:-0.02em;">
                {coif_fmt}
            </div>
        </div>
    </div>
    """


# ---------------------------------------------------------------------------
# Priority badge
# ---------------------------------------------------------------------------

def priority_badge(priority: str) -> str:
    """Return a coloured HTML badge for a priority level."""
    _map = {
        "Critical": ("badge-critical", "#ef4444"),
        "High":     ("badge-high",     "#f59e0b"),
        "Elevated": ("badge-elevated", "#c9a84c"),
        "Normal":   ("badge-normal",   "#10b981"),
        "Low":      ("badge-low",      "#8b92a5"),
    }
    cls, _ = _map.get(priority, ("badge-low", "#8b92a5"))
    return f'<span class="{cls}">{priority}</span>'
