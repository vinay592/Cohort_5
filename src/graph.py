"""
graph.py
--------
Build a directed dependency graph from interface_master (SourceSystem → TargetSystem),
annotate edges with CoIF-weighted event stats, and produce Plotly figures.
"""

from __future__ import annotations

from typing import Any

import networkx as nx
import pandas as pd
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_dependency_graph(
    interface_master: pd.DataFrame,
    enriched_events: pd.DataFrame,
) -> nx.DiGraph:
    """
    Build a directed graph where:
        nodes  = systems + middleware
        edges  = SourceSystem -> Middleware -> TargetSystem

    Edge attributes (aggregated from enriched_events):
        EventCount, FailedCount, WarningCount, TotalCoIF,
        TopErrorCodes, AffectedInterfaces
    """
    G = nx.DiGraph()

    # Add edges from interface_master (Source -> MW -> Target)
    for _, row in interface_master.iterrows():
        src = row["SourceSystem"]
        tgt = row["TargetSystem"]
        mw = row["Middleware"]
        mw_node = f"[{mw}]"  # e.g., [API], [MsgBus] to distinguish from systems

        G.add_node(src, type="System")
        G.add_node(tgt, type="System")
        G.add_node(mw_node, type="Middleware")

        for u, v in [(src, mw_node), (mw_node, tgt)]:
            if not G.has_edge(u, v):
                G.add_edge(u, v, EventCount=0, FailedCount=0,
                           WarningCount=0, TotalCoIF=0.0,
                           AffectedInterfaces=[], TopErrorCodes=[])

    # Annotate edges with event stats
    if enriched_events is not None and not enriched_events.empty:
        edge_agg = (
            enriched_events.groupby(["SourceSystem", "TargetSystem", "Middleware"])
            .agg(
                EventCount=("EventID", "count"),
                FailedCount=("Status", lambda s: (s == "Failed").sum()),
                WarningCount=("Status", lambda s: (s == "Warning").sum()),
                TotalCoIF=("CoIF", "sum"),
            )
            .reset_index()
        )

        top_errors = (
            enriched_events.groupby(["SourceSystem", "TargetSystem", "Middleware"])["ErrorCode"]
            .apply(lambda s: s.value_counts().head(3).index.tolist())
            .reset_index()
        )

        for _, erow in edge_agg.iterrows():
            src = erow["SourceSystem"]
            tgt = erow["TargetSystem"]
            mw = erow["Middleware"]
            mw_node = f"[{mw}]"
            
            for u, v in [(src, mw_node), (mw_node, tgt)]:
                if G.has_edge(u, v):
                    G[u][v]["EventCount"] += int(erow["EventCount"])
                    G[u][v]["FailedCount"] += int(erow["FailedCount"])
                    G[u][v]["WarningCount"] += int(erow["WarningCount"])
                    G[u][v]["TotalCoIF"] += float(erow["TotalCoIF"])
                    
        # for affected interfaces, append and deduplicate
        iface_by_edge = (
            enriched_events.groupby(["SourceSystem", "TargetSystem", "Middleware"])["InterfaceID"]
            .apply(lambda s: sorted(s.unique().tolist()))
            .reset_index()
        )
        for _, irow in iface_by_edge.iterrows():
            src = irow["SourceSystem"]
            tgt = irow["TargetSystem"]
            mw = irow["Middleware"]
            mw_node = f"[{mw}]"
            for u, v in [(src, mw_node), (mw_node, tgt)]:
                if G.has_edge(u, v):
                    existing = set(G[u][v]["AffectedInterfaces"])
                    existing.update(irow["InterfaceID"])
                    G[u][v]["AffectedInterfaces"] = sorted(list(existing))

        for _, terr in top_errors.iterrows():
            src = terr["SourceSystem"]
            tgt = terr["TargetSystem"]
            mw = terr["Middleware"]
            mw_node = f"[{mw}]"
            for u, v in [(src, mw_node), (mw_node, tgt)]:
                if G.has_edge(u, v):
                    G[u][v]["TopErrorCodes"] = terr["ErrorCode"]

    return G


# ---------------------------------------------------------------------------
# Plotly visualisation
# ---------------------------------------------------------------------------

_SYSTEM_FULL_NAMES = {
    "ORD": "Order System",
    "MFG": "Manufacturing",
    "PRC": "Procurement",
    "ASM": "Assembly",
    "DLV": "Delivery",
    "PAY": "Payment",
}


def graph_to_plotly(G: nx.DiGraph) -> go.Figure:
    """
    Render the dependency graph as a Plotly figure.
    Edge width and colour encode TotalCoIF (darker / thicker = higher impact).
    """
    if len(G.nodes) == 0:
        return go.Figure()

    pos = nx.spring_layout(G, seed=42, k=2.5)

    max_coif = max(
        (G[u][v].get("TotalCoIF", 0) for u, v in G.edges()), default=1
    ) or 1

    edge_traces = []
    annotation_arrows = []

    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        coif = data.get("TotalCoIF", 0)
        ratio = coif / max_coif

        # Color: low → steel blue, high → crimson
        r = int(30 + 200 * ratio)
        g_c = int(100 - 80 * ratio)
        b = int(200 - 170 * ratio)
        color = f"rgb({r},{g_c},{b})"
        width = 1.5 + 4.5 * ratio

        edge_traces.append(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode="lines",
                line=dict(width=width, color=color),
                hoverinfo="text",
                text=(
                    f"<b>{u} → {v}</b><br>"
                    f"Events: {data.get('EventCount', 0)}<br>"
                    f"Failed: {data.get('FailedCount', 0)}<br>"
                    f"Warning: {data.get('WarningCount', 0)}<br>"
                    f"Total CoIF: {coif:,.0f}<br>"
                    f"Top Errors: {', '.join(str(e) for e in data.get('TopErrorCodes', []))}"
                ),
                name=f"{u}→{v}",
            )
        )

        # Arrow annotation
        annotation_arrows.append(
            dict(
                ax=x0, ay=y0, x=x1, y=y1,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=3, arrowsize=1.2,
                arrowwidth=width * 0.6, arrowcolor=color,
            )
        )

    # Node traces
    node_x, node_y, node_text, node_hover = [], [], [], []
    node_color, node_size, node_symbol, node_line_color = [], [], [], []
    
    for node, ndata in G.nodes(data=True):
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        is_mw = ndata.get("type") == "Middleware"
        
        if is_mw:
            # Middleware styling
            node_text.append(f"<b>{node}</b>")
            node_color.append("#0f766e") # teal
            node_line_color.append("#5eead4")
            node_size.append(32)
            node_symbol.append("square")
            
            total_out_coif = sum(G[node][v].get("TotalCoIF", 0) for v in G.successors(node))
            total_in_coif = sum(G[u][node].get("TotalCoIF", 0) for u in G.predecessors(node))
            node_hover.append(
                f"<b>{node}</b> (Middleware)<br>"
                f"Outbound CoIF: {total_out_coif:,.0f}<br>"
                f"Inbound CoIF: {total_in_coif:,.0f}"
            )
        else:
            # System styling
            node_text.append(f"<b>{node}</b><br>{_SYSTEM_FULL_NAMES.get(node, node)}")
            node_color.append("#1e3a5f") # original dark blue
            node_line_color.append("#4fc3f7")
            node_size.append(42)
            node_symbol.append("circle")
            
            total_out_coif = sum(G[node][v].get("TotalCoIF", 0) for v in G.successors(node))
            total_in_coif = sum(G[u][node].get("TotalCoIF", 0) for u in G.predecessors(node))
            node_hover.append(
                f"<b>{node}</b> – {_SYSTEM_FULL_NAMES.get(node, node)}<br>"
                f"Outbound CoIF: {total_out_coif:,.0f}<br>"
                f"Inbound CoIF: {total_in_coif:,.0f}"
            )

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        hoverinfo="text",
        hovertext=node_hover,
        text=node_text,
        textposition="top center",
        textfont=dict(size=12, color="#e2e8f0"),
        marker=dict(
            symbol=node_symbol,
            size=node_size,
            color=node_color,
            line=dict(width=2.5, color=node_line_color),
        ),
    )

    fig = go.Figure(
        data=[*edge_traces, node_trace],
        layout=go.Layout(
            showlegend=False,
            paper_bgcolor="#0f172a",
            plot_bgcolor="#0f172a",
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            hovermode="closest",
            annotations=annotation_arrows,
            height=520,
        ),
    )
    return fig


def get_edge_data(G: nx.DiGraph, src: str, tgt: str) -> dict[str, Any]:
    """Return edge attribute dict or empty dict."""
    if G.has_edge(src, tgt):
        return dict(G[src][tgt])
    return {}
