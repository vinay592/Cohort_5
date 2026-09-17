"""
ui_l2_helpers.py
----------------
L2-specific Streamlit UI helpers and Plotly charts.
All functions return either Plotly figures or HTML strings.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


# ---------------------------------------------------------------------------
# Colour palette (consistent with L1 dark theme)
# ---------------------------------------------------------------------------
_TIER_COLORS = {
    "CRITICAL": "#f87171",   # red
    "HIGH":     "#fb923c",   # orange
    "MEDIUM":   "#fbbf24",   # amber
    "LOW":      "#4ade80",   # green
}

_RCA_COLORS = {
    "CHRONIC":       "#f87171",   # red
    "EVENT":         "#38bdf8",   # sky blue
    "CHRONIC_EVENT": "#fb923c",   # orange
}

_ESC_COLORS = {
    "P1": "#f87171",
    "P2": "#fb923c",
    "P3": "#fbbf24",
    "P4": "#4ade80",
}


# ---------------------------------------------------------------------------
# Badges (HTML)
# ---------------------------------------------------------------------------

def impact_tier_badge(tier: str) -> str:
    color = _TIER_COLORS.get(tier, "#94a3b8")
    return (
        f'<span style="background:rgba({_hex_to_rgb(color)},0.2); '
        f'color:{color}; border:1px solid {color}; '
        f'padding:2px 10px; border-radius:20px; '
        f'font-size:0.75rem; font-weight:700; letter-spacing:0.05em;">'
        f'{tier}</span>'
    )


def rca_category_badge(category: str) -> str:
    label_map = {
        "CHRONIC":       "🔴 CHRONIC",
        "EVENT":         "🔵 EVENT",
        "CHRONIC_EVENT": "🟠 MIXED",
    }
    color = _RCA_COLORS.get(category, "#94a3b8")
    label = label_map.get(category, category)
    return (
        f'<span style="background:rgba({_hex_to_rgb(color)},0.2); '
        f'color:{color}; border:1px solid {color}; '
        f'padding:2px 12px; border-radius:20px; '
        f'font-size:0.75rem; font-weight:700;">'
        f'{label}</span>'
    )


def escalation_badge(level: str) -> str:
    color = _ESC_COLORS.get(level, "#94a3b8")
    return (
        f'<span style="background:rgba({_hex_to_rgb(color)},0.2); '
        f'color:{color}; border:1px solid {color}; '
        f'padding:2px 10px; border-radius:20px; '
        f'font-size:0.75rem; font-weight:700;">'
        f'{level}</span>'
    )


def human_review_badge(required: bool) -> str:
    if required:
        return (
            '<span style="background:rgba(248,113,113,0.15); color:#f87171; '
            'border:1px solid #f87171; padding:2px 12px; border-radius:20px; '
            'font-size:0.75rem; font-weight:700;">⚠️ HUMAN REVIEW</span>'
        )
    return (
        '<span style="background:rgba(74,222,128,0.15); color:#4ade80; '
        'border:1px solid #4ade80; padding:2px 12px; border-radius:20px; '
        'font-size:0.75rem; font-weight:700;">✅ AUTO</span>'
    )


def _hex_to_rgb(h: str) -> str:
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def blast_radius_chart(enhanced_incidents: pd.DataFrame) -> go.Figure:
    """
    Bubble chart: x = EventCount, y = TotalCoIF, size = BlastRadius,
    color = ImpactTier. Adds slight jittering for overlapping clusters.
    """
    if enhanced_incidents.empty:
        return go.Figure()

    df = enhanced_incidents.copy()
    df["ImpactTier"] = df["ImpactTier"].fillna("LOW")
    df["BlastRadius"] = df["BlastRadius"].fillna(1).clip(lower=1)

    # Calculate jitter for overlapping points with identical EventCount and TotalCoIF
    import numpy as np
    np.random.seed(42)
    df["_x_jitter"] = df["EventCount"] + np.random.uniform(-0.15, 0.15, size=len(df))
    df["_y_jitter"] = df["TotalCoIF"] * (1 + np.random.uniform(-0.015, 0.015, size=len(df)))

    fig = go.Figure()
    for tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        subset = df[df["ImpactTier"] == tier]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset["_x_jitter"],
            y=subset["_y_jitter"],
            mode="markers",
            name=tier,
            marker=dict(
                size=subset["BlastRadius"].clip(lower=10, upper=55),
                color=_TIER_COLORS.get(tier, "#94a3b8"),
                opacity=0.8,
                line=dict(width=1.5, color="#0f172a"),
            ),
            text=subset.apply(
                lambda r: (
                    f"<b>{r['IncidentID']}</b><br>"
                    f"Impact Tier: {r['ImpactTier']}<br>"
                    f"Events: {r['EventCount']}<br>"
                    f"Total CoIF: {r['TotalCoIF']:,.0f}<br>"
                    f"Blast Radius: {r['BlastRadius']:.1f}/100<br>"
                    f"Systems: {', '.join(r['AffectedSystems']) if isinstance(r['AffectedSystems'], list) else r['AffectedSystems']}"
                ), axis=1
            ),
            hovertemplate="%{text}<extra></extra>",
        ))

    fig.update_layout(
        title=dict(
            text="Blast Radius Map — Bubble size = Impact spread",
            font=dict(color="#e2e8f0", size=14),
        ),
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        xaxis=dict(
            title="Event Count", color="#94a3b8",
            gridcolor="#1e293b", zeroline=False,
        ),
        yaxis=dict(
            title="Total CoIF", color="#94a3b8",
            gridcolor="#1e293b", zeroline=False,
        ),
        legend=dict(
            title="Impact Tier", font=dict(color="#e2e8f0"),
            bgcolor="#1e293b", bordercolor="#334155",
        ),
        margin=dict(l=20, r=20, t=50, b=20),
        height=420,
    )
    return fig


def rca_distribution_chart(rca_df: pd.DataFrame) -> go.Figure:
    """Donut chart: breakdown of CHRONIC / EVENT / CHRONIC_EVENT by count and CoIF."""
    if rca_df.empty:
        return go.Figure()

    counts = rca_df["RCACategory"].value_counts().reset_index()
    counts.columns = ["Category", "Count"]
    counts["Color"] = counts["Category"].map(_RCA_COLORS).fillna("#94a3b8")

    fig = go.Figure(go.Pie(
        labels=counts["Category"],
        values=counts["Count"],
        hole=0.55,
        marker=dict(colors=counts["Color"].tolist(),
                    line=dict(color="#0f172a", width=2)),
        textinfo="label+percent",
        textfont=dict(color="#e2e8f0", size=12),
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Share: %{percent}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text="RCA Classification — Chronic vs Event breakdown",
            font=dict(color="#e2e8f0", size=14),
        ),
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        legend=dict(font=dict(color="#e2e8f0"), bgcolor="#1e293b"),
        margin=dict(l=20, r=20, t=50, b=20),
        height=350,
        showlegend=True,
        annotations=[dict(
            text=f"<b>{len(rca_df)}</b><br>incidents",
            x=0.5, y=0.5, font=dict(size=14, color="#e2e8f0"),
            showarrow=False,
        )],
    )
    return fig


def remediation_summary_chart(remediation_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar: incidents per team, coloured by escalation level."""
    if remediation_df.empty:
        return go.Figure()

    team_counts = (
        remediation_df
        .groupby(["AssignedTeam", "EscalationLevel"])
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=True)
    )

    colors = team_counts["EscalationLevel"].map(_ESC_COLORS).fillna("#94a3b8")

    fig = go.Figure(go.Bar(
        x=team_counts["Count"],
        y=team_counts["AssignedTeam"],
        orientation="h",
        marker=dict(color=colors.tolist(), opacity=0.85),
        text=team_counts["EscalationLevel"],
        textposition="inside",
        textfont=dict(color="#0f172a", size=11, family="monospace"),
        hovertemplate="<b>%{y}</b><br>Incidents: %{x}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text="Incident Routing — Incidents per team",
            font=dict(color="#e2e8f0", size=14),
        ),
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        xaxis=dict(
            title="Incident Count", color="#94a3b8",
            gridcolor="#1e293b", zeroline=False,
        ),
        yaxis=dict(color="#e2e8f0", tickfont=dict(size=11)),
        margin=dict(l=20, r=20, t=50, b=20),
        height=max(250, 40 * len(team_counts) + 80),
    )
    return fig


def incident_detail_card(rca_row: pd.Series) -> str:
    """Render a styled HTML card for a single incident's RCA result."""
    tier_badge = impact_tier_badge(str(rca_row.get("ImpactTier", "LOW")))
    rca_badge  = rca_category_badge(str(rca_row.get("RCACategory", "EVENT")))
    conf       = int(float(rca_row.get("ConfidenceScore", 0.5)) * 100)

    conf_color = "#4ade80" if conf >= 80 else "#fbbf24" if conf >= 60 else "#f87171"

    return f"""
    <div style="background:#1e293b; border:1px solid #1e3a5f;
                border-radius:12px; padding:20px; margin-bottom:12px;">
        <div style="display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap;">
            {tier_badge} {rca_badge}
        </div>
        <table style="width:100%; border-collapse:collapse;">
            <tr><td style="color:#94a3b8; padding:5px 0; width:180px;">Root Cause Interface</td>
                <td style="color:#a78bfa; font-weight:600;">{rca_row.get('RootCauseInterface','—')}</td></tr>
            <tr><td style="color:#94a3b8; padding:5px 0;">Root Cause System</td>
                <td style="color:#e2e8f0;">{rca_row.get('RootCauseSystem','—')}</td></tr>
            <tr><td style="color:#94a3b8; padding:5px 0;">Primary Error</td>
                <td style="color:#e2e8f0; font-family:monospace;">{rca_row.get('PrimaryErrorCode','—')}</td></tr>
            <tr><td style="color:#94a3b8; padding:5px 0;">Historical Recurrence</td>
                <td style="color:#e2e8f0;">{rca_row.get('RecurrenceCount','—')} times in dataset</td></tr>
            <tr><td style="color:#94a3b8; padding:5px 0;">Incident Duration</td>
                <td style="color:#e2e8f0;">{rca_row.get('IncidentDuration_min','—')} min</td></tr>
            <tr><td style="color:#94a3b8; padding:5px 0;">RCA Confidence</td>
                <td style="color:{conf_color}; font-weight:700;">{conf}%</td></tr>
            <tr><td style="color:#94a3b8; padding:5px 0;">Blast Radius</td>
                <td style="color:#e2e8f0;">{rca_row.get('BlastRadius','—')}/100</td></tr>
        </table>
    </div>
    """


def remediation_detail_card(rem_row: pd.Series) -> str:
    """Render a styled HTML card for a single incident's remediation plan."""
    esc_badge   = escalation_badge(str(rem_row.get("EscalationLevel", "P4")))
    human_badge = human_review_badge(bool(rem_row.get("HumanReviewRequired", False)))

    return f"""
    <div style="background:#1e293b; border:1px solid #1e3a5f;
                border-radius:12px; padding:20px; margin-bottom:12px;">
        <div style="display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap;">
            {esc_badge} {human_badge}
        </div>
        <table style="width:100%; border-collapse:collapse; margin-bottom:12px;">
            <tr><td style="color:#94a3b8; padding:5px 0; width:180px;">Assigned Team</td>
                <td style="color:#38bdf8; font-weight:600;">{rem_row.get('AssignedTeam','—')}</td></tr>
            <tr><td style="color:#94a3b8; padding:5px 0;">Est. Resolution</td>
                <td style="color:#e2e8f0;">{rem_row.get('EstimatedResolution_min','—')} min</td></tr>
            <tr><td style="color:#94a3b8; padding:5px 0;">Auto-Resolvable</td>
                <td style="color:#e2e8f0;">{'✅ Yes' if rem_row.get('AutoResolvable') else '❌ No'}</td></tr>
            <tr><td style="color:#94a3b8; padding:5px 0;">Human Review Reason</td>
                <td style="color:#fbbf24; font-size:0.85rem;">{rem_row.get('HumanReviewReason') or '—'}</td></tr>
        </table>
    </div>
    """


def playbook_card(steps: list) -> str:
    """Render numbered playbook steps as styled HTML."""
    if not steps:
        return "<p style='color:#94a3b8;'>No playbook steps available.</p>"
    items = "".join(
        f'<li style="color:#e2e8f0; padding:6px 0; border-bottom:1px solid #1e3a5f; font-size:0.9rem;">{s}</li>'
        for s in steps
    )
    return f"""
    <div style="background:#0f172a; border:1px solid #1e3a5f;
                border-radius:10px; padding:16px; margin-top:8px;">
        <div style="color:#c9a84c; font-size:0.7rem; text-transform:uppercase;
                    letter-spacing:0.1em; font-weight:600; margin-bottom:10px;">
            📋 Remediation Playbook
        </div>
        <ol style="margin:0; padding-left:20px;">{items}</ol>
    </div>
    """
