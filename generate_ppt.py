"""
generate_ppt.py
---------------
Generates the complete hackathon presentation as a .pptx file.
Run with: python3 generate_ppt.py
Output:   Integration_Health_Platform.pptx
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from pptx.enum.dml import MSO_THEME_COLOR
import pptx.oxml.ns as ns
from lxml import etree
import copy

# ── Colour Palette ────────────────────────────────────────────────────────────
BG_DARK      = RGBColor(0x0F, 0x17, 0x2A)   # #0f172a slate-900
BG_CARD      = RGBColor(0x1E, 0x29, 0x3B)   # #1e293b slate-800
ACCENT_BLUE  = RGBColor(0x38, 0xBD, 0xF8)   # #38bdf8 sky-400
ACCENT_TEAL  = RGBColor(0x2D, 0xD4, 0xBF)   # #2dd4bf teal-400
ACCENT_AMBER = RGBColor(0xFB, 0xBF, 0x24)   # #fbbf24 amber-400
ACCENT_RED   = RGBColor(0xF8, 0x71, 0x71)   # #f87171 red-400
ACCENT_GREEN = RGBColor(0x4A, 0xDE, 0x80)   # #4ade80 green-400
TEXT_PRIMARY = RGBColor(0xF1, 0xF5, 0xF9)   # #f1f5f9
TEXT_MUTED   = RGBColor(0x94, 0xA3, 0xB8)   # #94a3b8
WHITE        = RGBColor(0xFF, 0xFF, 0xFF)

W, H = Inches(13.33), Inches(7.5)   # 16:9 widescreen

prs = Presentation()
prs.slide_width  = W
prs.slide_height = H
blank = prs.slide_layouts[6]   # blank layout used for all slides


# ── Helpers ───────────────────────────────────────────────────────────────────
def add_slide():
    sl = prs.slides.add_slide(blank)
    bg = sl.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = BG_DARK
    return sl

def txb(sl, text, x, y, w, h, size=18, bold=False, color=TEXT_PRIMARY,
        align=PP_ALIGN.LEFT, wrap=True, italic=False):
    tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = "Calibri"
    return tb

def rect(sl, x, y, w, h, fill=BG_CARD, radius=False, line_color=None, line_width=Pt(1)):
    shape = sl.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = line_width
    else:
        shape.line.fill.background()
    return shape

def arrow(sl, x1, y1, x2, y2, color=ACCENT_BLUE, width=Pt(2.5)):
    """Draw a line with an arrowhead from (x1,y1) to (x2,y2) in inches."""
    connector = sl.shapes.add_connector(
        1,  # STRAIGHT
        Inches(x1), Inches(y1), Inches(x2), Inches(y2)
    )
    connector.line.color.rgb = color
    connector.line.width = width
    return connector

def badge(sl, text, x, y, w=1.4, h=0.38, fill=ACCENT_BLUE, tcolor=BG_DARK, size=13):
    r = rect(sl, x, y, w, h, fill=fill)
    txb(sl, text, x+0.05, y+0.04, w-0.1, h-0.08, size=size, bold=True,
        color=tcolor, align=PP_ALIGN.CENTER)
    return r

def divider_line(sl, y, x1=0.4, x2=12.9, color=ACCENT_BLUE):
    ln = sl.shapes.add_connector(1, Inches(x1), Inches(y), Inches(x2), Inches(y))
    ln.line.color.rgb = color
    ln.line.width = Pt(0.75)

def section_label(sl, text, color=ACCENT_BLUE):
    txb(sl, text, 0.4, 0.22, 6, 0.4, size=11, bold=True, color=color)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — Title Slide
# ══════════════════════════════════════════════════════════════════════════════
sl = add_slide()

# Title accent bar
rect(sl, 0, 0, 13.33, 0.08, fill=ACCENT_BLUE)
rect(sl, 0, 7.42, 13.33, 0.08, fill=ACCENT_BLUE)

txb(sl, "Integration Health Monitoring Platform",
    0.7, 1.6, 11.9, 1.4, size=44, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

txb(sl, "CoIF · Log Normalization · Incident Correlation · Evidence-Grounded RCA",
    0.7, 3.1, 11.9, 0.6, size=18, color=ACCENT_BLUE, align=PP_ALIGN.CENTER)

divider_line(sl, 3.85, 3.5, 9.8, ACCENT_TEAL)

# L-badges
for label, col, lx in [("L1 COMPLETE", ACCENT_GREEN, 3.8),
                        ("L2 STAGE 1+2 COMPLETE", ACCENT_AMBER, 5.6),
                        ("L3 DESIGNED", ACCENT_RED, 8.6)]:
    badge(sl, label, lx, 4.1, w=1.8 if "2" in label else 1.4, fill=col, tcolor=BG_DARK, size=12)

txb(sl, "NCG Hackathon · Integration Health Monitoring",
    0.7, 6.8, 11.9, 0.5, size=13, color=TEXT_MUTED, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — The Problem
# ══════════════════════════════════════════════════════════════════════════════
sl = add_slide()
section_label(sl, "PART 1  ·  THE PROBLEM")
txb(sl, "Enterprise Integration: A Visibility Blackhole",
    0.4, 0.55, 12, 0.65, size=30, bold=True, color=WHITE)

# Problem statement card
rect(sl, 0.4, 1.35, 12.5, 1.1, fill=BG_CARD, line_color=ACCENT_BLUE)
txb(sl, "Build an AI-powered Integration Health Monitoring platform that ingests "
        "messy multi-format logs · presents a business-impact-weighted health map · "
        "detects failures & anomalies · correlates events into incidents · explains "
        "root cause (chronic vs. event) with prescriptive remediation · predicts "
        "change/upgrade blast-radius before deployment.",
    0.6, 1.45, 12.1, 0.9, size=13, color=TEXT_PRIMARY)

# Architecture diagram — nodes and arrows
# Nodes: SAP → KAFKA → ORACLE
for label, lx, fill_c in [("SAP ERP", 1.0, BG_CARD),
                           ("Kafka / ESB", 5.8, BG_CARD),
                           ("Oracle SCM", 10.0, BG_CARD)]:
    r = rect(sl, lx, 2.7, 2.0, 0.65, fill=fill_c, line_color=ACCENT_BLUE)
    txb(sl, label, lx, 2.75, 2.0, 0.55, size=14, bold=True,
        color=ACCENT_BLUE, align=PP_ALIGN.CENTER)

# arrows between nodes
arrow(sl, 3.0, 3.025, 5.8, 3.025, ACCENT_AMBER)
arrow(sl, 7.8, 3.025, 10.0, 3.025, ACCENT_AMBER)

# "Failure gap" label
txb(sl, "⚠ Integration Failures Happen Here", 3.9, 2.4, 3.5, 0.4,
    size=11, bold=True, color=ACCENT_AMBER, align=PP_ALIGN.CENTER)

# Sub-apps under SAP
for sub, sy in [("Production Planning", 3.65), ("Quality Management", 4.2)]:
    rect(sl, 0.7, sy, 1.7, 0.38, fill=BG_CARD, line_color=TEXT_MUTED)
    txb(sl, sub, 0.72, sy+0.04, 1.66, 0.3, size=10, color=TEXT_MUTED, align=PP_ALIGN.CENTER)
    arrow(sl, 2.0, 3.35, 2.0, sy+0.19, TEXT_MUTED)

# Sub-apps under Oracle
for sub, sy in [("Supply Chain Mgmt", 3.65), ("Inventory Mgmt", 4.2)]:
    rect(sl, 10.9, sy, 1.7, 0.38, fill=BG_CARD, line_color=TEXT_MUTED)
    txb(sl, sub, 10.92, sy+0.04, 1.66, 0.3, size=10, color=TEXT_MUTED, align=PP_ALIGN.CENTER)
    arrow(sl, 11.0, 3.35, 11.0, sy+0.19, TEXT_MUTED)

# Bottom flow
txb(sl, "Product Planning  →  SAP  →  Kafka  →  Oracle  →  Supply Chain",
    2.0, 4.85, 9.0, 0.4, size=13, bold=True, color=TEXT_MUTED, align=PP_ALIGN.CENTER)

# 4 success pillars
for icon, label, lx in [("🎯", "Prioritize\nby business impact", 0.5),
                         ("🧠", "Explain\nRoot cause in evidence", 3.55),
                         ("🔧", "Prescribe\nFix to right queue", 6.6),
                         ("⚡", "Predict\nBlast-radius pre-deploy", 9.6)]:
    rect(sl, lx, 5.4, 2.8, 1.7, fill=BG_CARD, line_color=ACCENT_TEAL)
    txb(sl, icon, lx, 5.45, 2.8, 0.55, size=22, align=PP_ALIGN.CENTER)
    txb(sl, label, lx, 5.95, 2.8, 0.9, size=12, bold=True,
        color=TEXT_PRIMARY, align=PP_ALIGN.CENTER)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — Agentic Log Normalization
# ══════════════════════════════════════════════════════════════════════════════
sl = add_slide()
section_label(sl, "PART 2  ·  CONVERTING MESSY LOGS TO CONSISTENT EVENTS")
txb(sl, "Agentic Log Normalization Pipeline",
    0.4, 0.55, 12, 0.65, size=30, bold=True, color=WHITE)

# Source systems — left column
txb(sl, "HETEROGENEOUS SOURCES", 0.3, 1.35, 3.0, 0.35, size=11, bold=True, color=ACCENT_AMBER)
sources = [("SAP ERP", "Pipe-delimited text"), ("Oracle SCM", "Nested JSON Lines"),
           ("MES", "Key=Value Runtime Log"), ("PLM", "XML Event Records"),
           ("CRM", "Semicolon Audit Trail"), ("HCM", "CSV (proprietary codes)")]
for i, (name, fmt) in enumerate(sources):
    ry = 1.75 + i * 0.75
    rect(sl, 0.3, ry, 2.8, 0.6, fill=BG_CARD, line_color=ACCENT_AMBER)
    txb(sl, name, 0.35, ry+0.03, 2.7, 0.28, size=12, bold=True, color=ACCENT_AMBER)
    txb(sl, fmt, 0.35, ry+0.3, 2.7, 0.25, size=9, color=TEXT_MUTED)

# Arrows from sources to orchestrator
for i in range(6):
    arrow(sl, 3.1, 1.75+i*0.75+0.3, 3.9, 3.7, ACCENT_AMBER, Pt(1.5))

# Orchestrator steps — center
txb(sl, "AGENTIC ORCHESTRATOR", 3.9, 1.35, 5.5, 0.35, size=11, bold=True, color=ACCENT_BLUE)
steps = [
    ("1  Extract Schema", ACCENT_BLUE),
    ("2  Sample Records", ACCENT_BLUE),
    ("3  LLM → Semantic Mapping + Code", ACCENT_TEAL),
    ("4  Execute in Sandbox", ACCENT_TEAL),
    ("5  Validate 14-col Contract", ACCENT_GREEN),
]
for i, (step, col) in enumerate(steps):
    ry = 1.75 + i * 0.88
    rect(sl, 3.9, ry, 5.3, 0.65, fill=BG_CARD, line_color=col)
    txb(sl, step, 4.0, ry+0.13, 5.1, 0.38, size=13, bold=True, color=col)
    if i < 4:
        arrow(sl, 6.55, ry+0.65, 6.55, ry+0.88, col, Pt(2))

# Arrows from orchestrator to output
for i in range(3):
    arrow(sl, 9.2, 2.5+i*0.88, 9.9, 4.0, ACCENT_GREEN, Pt(1.5))

# Normalized output — right column
txb(sl, "NORMALIZED SCHEMA (14 cols)", 9.9, 1.35, 3.0, 0.35, size=11, bold=True, color=ACCENT_GREEN)
fields = ["EventID", "InterfaceID", "SourceSystem", "TargetSystem",
          "Middleware", "Pattern", "Status", "ErrorCode",
          "ErrorText", "RootCauseClass", "Latency_ms",
          "SessionID", "RequestID", "Timestamp"]
for i, f in enumerate(fields):
    col = ACCENT_GREEN if i < 7 else TEXT_MUTED
    txb(sl, f"• {f}", 10.0, 1.75+i*0.35, 2.8, 0.33, size=11, color=col)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — CoIF Formula
# ══════════════════════════════════════════════════════════════════════════════
sl = add_slide()
section_label(sl, "PART 3  ·  COST OF INTEGRATION FAILURE  (CoIF)")
txb(sl, "Quantifying Business Impact — Not Raw Failure Count",
    0.4, 0.55, 12, 0.65, size=30, bold=True, color=WHITE)

# Formula Box
rect(sl, 0.4, 1.3, 12.5, 1.1, fill=BG_CARD, line_color=ACCENT_BLUE, line_width=Pt(2))
txb(sl, "CoIF  =  Failure Signal  ×  Priority Weight  ×  Process Weight  ×  Cost Multiplier",
    0.6, 1.42, 12.1, 0.6, size=22, bold=True, color=ACCENT_BLUE, align=PP_ALIGN.CENTER)
txb(sl, "Each event gets a CoIF score  ·  TotalCoIF per interface = SUM of all event scores",
    0.6, 1.9, 12.1, 0.35, size=12, color=TEXT_MUTED, align=PP_ALIGN.CENTER)

# Factor breakdown cards
factors = [
    ("Failure Signal", "Failed = 1.0\nRetry = 0.3\nWarning = 0.5\nSuccess = 0.0", ACCENT_RED),
    ("Priority Weight", "Critical = 100\nHigh = 60\nElevated = 25\nNormal = 5 · Low = 2", ACCENT_AMBER),
    ("Process Weight", "Goods Receipt = 100\nIncident Sync = 15\nDemand Sync = 20\n(from piw table)", ACCENT_TEAL),
    ("Cost Multiplier", "Month-End Close = 3.0×\nQuarter-End Close = 2.0×\nNormal = 1.0×", ACCENT_BLUE),
]
for i, (title, body, col) in enumerate(factors):
    lx = 0.4 + i * 3.25
    rect(sl, lx, 2.55, 3.05, 2.2, fill=BG_CARD, line_color=col)
    txb(sl, title, lx+0.1, 2.6, 2.85, 0.4, size=13, bold=True, color=col)
    txb(sl, body, lx+0.1, 3.05, 2.85, 1.5, size=11, color=TEXT_PRIMARY)

# Example calculation
rect(sl, 0.4, 4.9, 12.5, 0.75, fill=BG_CARD, line_color=ACCENT_TEAL)
txb(sl, "Example:  FAILED event · Critical Interface · Payment Process · During Month-End",
    0.6, 4.95, 12.0, 0.3, size=12, color=TEXT_MUTED)
txb(sl, "CoIF  =  1.0  ×  100  ×  90  ×  3.0  =  27,000  →  Top priority for remediation",
    0.6, 5.27, 12.0, 0.32, size=14, bold=True, color=ACCENT_GREEN)

# Why not raw count
rect(sl, 0.4, 5.8, 12.5, 1.35, fill=BG_CARD, line_color=ACCENT_AMBER)
txb(sl, "⚠  Why not raw failure count?", 0.6, 5.85, 6.0, 0.35, size=13, bold=True, color=ACCENT_AMBER)
txb(sl, "Interface A: 500 failures   ·   Low-priority batch CRM sync   ·   Normal period",
    0.6, 6.22, 12.0, 0.28, size=12, color=TEXT_MUTED)
txb(sl, "Interface B:     5 failures  ·   Critical Payment Authorization  ·   Month-End Close  →  CoIF wins every time.",
    0.6, 6.55, 12.0, 0.28, size=12, bold=True, color=ACCENT_GREEN)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — CoIF Tradeoffs: Baseline vs ML
# ══════════════════════════════════════════════════════════════════════════════
sl = add_slide()
section_label(sl, "PART 3  ·  COIF TRADEOFFS: BASELINE FORMULA  vs  ML MODEL")
txb(sl, "Deterministic vs. Predictive CoIF", 0.4, 0.55, 12, 0.65, size=30, bold=True, color=WHITE)

# Headers
for label, col, lx in [("BASELINE FORMULA  (Implemented ✅)", ACCENT_GREEN, 0.4),
                        ("ML MODEL  (Future Roadmap 🚀)", ACCENT_AMBER, 6.8)]:
    rect(sl, lx, 1.3, 6.1, 0.55, fill=col)
    txb(sl, label, lx+0.15, 1.37, 5.8, 0.38, size=14, bold=True,
        color=BG_DARK, align=PP_ALIGN.CENTER)

# Pros / Cons for each
baseline_pros = ["✅  100% Explainable & auditable", "✅  Cold-start — works day one, zero training data",
                 "✅  Deterministic — same inputs → same score", "✅  Business user can verify any score by hand"]
baseline_cons = ["❌  Static weights — no adaptation to change",
                 "❌  Linear — misses cascading failure amplification",
                 "❌  Reactive — cannot predict future failures"]

ml_pros = ["✅  Adapts dynamically to shifting business conditions",
           "✅  Models cascading / non-linear impact propagation",
           "✅  Predictive — flags at-risk interfaces before failure"]
ml_cons = ["❌  Requires weeks of labelled historical data",
           "❌  Black-box — harder to explain to business stakeholders",
           "❌  Higher infrastructure & retraining overhead"]

txb(sl, "Advantages", 0.55, 1.95, 5.8, 0.35, size=12, bold=True, color=ACCENT_GREEN)
for i, t in enumerate(baseline_pros):
    txb(sl, t, 0.55, 2.3+i*0.48, 5.8, 0.42, size=12, color=TEXT_PRIMARY)

txb(sl, "Limitations", 0.55, 4.35, 5.8, 0.35, size=12, bold=True, color=ACCENT_RED)
for i, t in enumerate(baseline_cons):
    txb(sl, t, 0.55, 4.7+i*0.48, 5.8, 0.42, size=12, color=TEXT_MUTED)

txb(sl, "Advantages", 6.95, 1.95, 5.8, 0.35, size=12, bold=True, color=ACCENT_GREEN)
for i, t in enumerate(ml_pros):
    txb(sl, t, 6.95, 2.3+i*0.48, 5.8, 0.42, size=12, color=TEXT_PRIMARY)

txb(sl, "Limitations", 6.95, 4.35, 5.8, 0.35, size=12, bold=True, color=ACCENT_RED)
for i, t in enumerate(ml_cons):
    txb(sl, t, 6.95, 4.7+i*0.48, 5.8, 0.42, size=12, color=TEXT_MUTED)

# Recommendation
rect(sl, 0.4, 6.55, 12.5, 0.7, fill=BG_CARD, line_color=ACCENT_TEAL, line_width=Pt(2))
txb(sl, "💡  Recommended Production Approach: Hybrid — Hardcoded formula for real-time baseline + "
        "ML 'Risk Signal' as a separate predictive layer. Explainability of formula + adaptability of ML.",
    0.6, 6.6, 12.1, 0.55, size=12, bold=False, color=TEXT_PRIMARY)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 6 — L2 Pipeline Progress
# ══════════════════════════════════════════════════════════════════════════════
sl = add_slide()
section_label(sl, "PART 4  ·  L2 ADVANCED PIPELINE — IMPLEMENTATION STATUS")
txb(sl, "3-Stage L2 Pipeline: Built, Designed & Roadmapped",
    0.4, 0.55, 12, 0.65, size=30, bold=True, color=WHITE)

stages = [
    ("Stage 1", "Detect + Correlate", ACCENT_GREEN, "✅ COMPLETE",
     ["Temporal clustering: events on same interface within 5-min window merged",
      "Error-class clustering: same ErrorCode + RootCauseClass across interfaces merged",
      "Dependency clustering: events on connected interfaces (per graph) merged",
      "Algorithm: Union-Find on 3 simultaneous correlation signals → incident groups"]),
    ("Stage 2", "RCA — Chronic vs. Event", ACCENT_GREEN, "✅ COMPLETE",
     ["Chronic: recurring failures on same interface across multiple time windows",
      "Event-driven: failure burst correlates with a preceding change_event row",
      "Evidence-grounded NL Q&A: 8 question types → deterministic pandas queries",
      "Zero hallucination: LLM routes intent; SQL-like queries return actual rows"]),
    ("Stage 3", "Remediation & Human-in-Loop", ACCENT_AMBER, "⏳ DESIGNED",
     ["Auto-route incidents to correct L1–L4 queues via escalation_routing.csv",
      "Prescriptive fix suggestions per RootCauseClass",
      "Human-in-loop approval for Critical/P1 actions",
      "Self-learning loop to improve routing accuracy over time"]),
]
for i, (stage, title, col, status, bullets) in enumerate(stages):
    lx, ly = 0.4 + i * 4.3, 1.35
    rect(sl, lx, ly, 4.0, 0.55, fill=col)
    txb(sl, f"{stage}  ·  {status}", lx+0.1, ly+0.08, 3.8, 0.38,
        size=13, bold=True, color=BG_DARK, align=PP_ALIGN.CENTER)
    rect(sl, lx, ly+0.55, 4.0, 0.45, fill=BG_CARD, line_color=col)
    txb(sl, title, lx+0.1, ly+0.6, 3.8, 0.35, size=14, bold=True,
        color=col, align=PP_ALIGN.CENTER)
    for j, b in enumerate(bullets):
        txb(sl, f"• {b}", lx+0.1, ly+1.1+j*0.62, 3.8, 0.55, size=10.5, color=TEXT_PRIMARY)

# What L1 fully delivers
rect(sl, 0.4, 6.2, 12.5, 1.05, fill=BG_CARD, line_color=ACCENT_BLUE)
txb(sl, "L1 Fully Delivered  →  Ingest · Normalize · CoIF Health Map · Incident Correlation · Evidence NL Q&A · Dependency Graph",
    0.6, 6.28, 12.0, 0.35, size=12, bold=True, color=ACCENT_BLUE)
txb(sl, "Live Streamlit Dashboard running at http://localhost:8501",
    0.6, 6.65, 12.0, 0.35, size=12, color=TEXT_MUTED)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 7 — Future Scope / Roadmap
# ══════════════════════════════════════════════════════════════════════════════
sl = add_slide()
section_label(sl, "PART 5  ·  FUTURE SCOPE & ROADMAP")
txb(sl, "From Reactive Monitoring to Autonomous Remediation",
    0.4, 0.55, 12, 0.65, size=30, bold=True, color=WHITE)

# Staircase steps
steps_data = [
    (0.5, 5.5, 2.8, 0.95, ACCENT_TEAL,  "STEP 1 — Reactive  ✅",   "L1 Complete\nCoIF Health Map\nNL Q&A"),
    (3.5, 4.4, 2.8, 0.95, ACCENT_GREEN, "STEP 2 — Correlated  ✅",  "L2 Stage 1+2\nIncident Clustering\nChronic vs. Event RCA"),
    (6.5, 3.3, 2.8, 0.95, ACCENT_AMBER, "STEP 3 — Predictive  🚀",  "L3 Blast-Radius\nGraph Neural Networks\nRanked Risk per Interface"),
    (9.5, 2.2, 2.8, 0.95, ACCENT_RED,   "STEP 4 — Autonomous  🔮",  "Closed-Loop Healing\nAuto-Routing L1–L4\nSelf-Learning Weights"),
]
# Draw staircase connectors
for i, (lx, ly, w, h, col, title, body) in enumerate(steps_data):
    rect(sl, lx, ly, w, 1.9, fill=BG_CARD, line_color=col, line_width=Pt(2))
    txb(sl, title, lx+0.1, ly+0.08, w-0.2, 0.42, size=11, bold=True, color=col)
    txb(sl, body, lx+0.1, ly+0.52, w-0.2, 1.2, size=10.5, color=TEXT_PRIMARY)
    if i < 3:
        arrow(sl, lx+w, ly+0.95, lx+w+0.1, ly+0.95-1.1, col, Pt(2.5))

# Three future items
future = [
    ("🧠  L3 Blast-Radius Prediction", "GNNs on the dependency graph to compute ranked risk\nscore per interface for any proposed change event."),
    ("🔄  Real-Time Streaming Ingest", "Replace batch CSV ingestion with Kafka consumer streams.\nHealth Map updates within seconds of new failure events."),
    ("🤖  Closed-Loop Remediation", "Auto-route incidents to L1–L4 queues via escalation\nrouting table with human-in-loop for Critical actions."),
]
for i, (title, body) in enumerate(future):
    lx = 0.4 + i * 4.3
    rect(sl, lx, 5.65, 4.1, 1.55, fill=BG_CARD, line_color=ACCENT_BLUE)
    txb(sl, title, lx+0.15, 5.72, 3.8, 0.42, size=12, bold=True, color=ACCENT_BLUE)
    txb(sl, body, lx+0.15, 6.18, 3.8, 0.9, size=11, color=TEXT_PRIMARY)


# ══════════════════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════════════════
OUT = "Integration_Health_Platform.pptx"
prs.save(OUT)
print(f"✅  Saved → {OUT}  ({prs.slides.__len__()} slides)")
