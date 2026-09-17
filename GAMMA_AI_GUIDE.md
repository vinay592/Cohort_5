# Gamma AI Prompt: Integration Health Monitoring Platform
## NCG Hackathon — Cohort 5

**System Instructions for Gamma AI:**
You are an expert presentation designer. Create a highly concise, visually rich, dark-themed presentation based on the 5 parts below. Rely on diagrams, flowcharts, comparison tables, and architecture visuals — not text blocks. Keep bullets tight: max 6–8 words per bullet. Use the color palette: dark navy background (#0f172a), sky-blue accents (#38bdf8), teal highlights (#2dd4bf), amber warnings (#fbbf24).

---

## Part 1: Intro to Problem

**Title:** Enterprise Integration — A Visibility Blackhole

**Core Message (2 sentences max on slide):**
Enterprises run 6+ ERP systems exchanging data through middleware. When integrations fail, logs are unreadable, formats clash, and there is no unified health view — only raw failure counts that misprioritize business impact.

**Diagram 1 — Architecture Overview (dark, hand-drawn style):**
Draw a two-tier architecture diagram:
- Top row: `ERP System 1 (SAP)` ←→ `MIDDLEWARE (Kafka / ESB / REST_API)` ←→ `ERP System 2 (Oracle SCM)`
- Under SAP: Production Planning App, Quality Management App (each with sub-services)
- Under Oracle: Supply Chain App, Inventory Management App
- Bottom linear flow: `Product Planning → SAP → Kafka → Oracle → Supply Chain`
- Annotate the arrows between systems with a red/amber "⚠ Failure Gap — 6 different log formats, zero unified view"

**Diagram 2 — Problem Definition Cards (4 cards, icon + 1-line text):**
- 🎯 Prioritize — Rank by business impact, not raw failure count
- 🧠 Explain — Chronic vs. event-driven root cause, grounded in evidence
- 🔧 Prescribe — Right fix routed to the right support queue
- ⚡ Predict — Blast-radius risk score before a change deploys

---

## Part 2: Agentic Log Normalization

**Title:** Taming 6 Proprietary Formats with One Agentic Pipeline

**Core Message:**
We built an AI Orchestrator that reads any log format, generates a Python converter, runs it in a sandbox, validates the 14-column output — and produces a unified events table without a single hard-coded parser.

**Diagram — Left-to-Right Agentic Flow (3 zones, use arrows between each step):**

**Zone 1 — Heterogeneous Inputs (left column, 6 boxes):**
| System | Format |
|--------|--------|
| SAP ERP | Pipe-delimited: `EVT\|TS\|IFACE\|RESULT\|DETAILS` |
| Oracle SCM | Nested JSON Lines (origin, destination, transport objects) |
| MES | Double-pipe Key=Value: `WHEN=...\|\|TXN=...\|\|CONTEXT={...}` |
| PLM | XML: `<event id="..." status="..."><failure code="...">` |
| CRM | Semicolon-delimited audit trail |
| HCM | CSV with custom vocabulary (state_code=9 means FAILED) |

**Zone 2 — Agentic Orchestrator (center, 5 numbered steps with arrows between them):**
1. Extract structural schema from raw file
2. Sample representative records (success + failure examples)
3. LLM → Generate semantic field mapping + Python converter code
4. Execute converter in sandboxed subprocess (timeout enforced)
5. Validate: 14 columns, correct types, no nulls in required fields

**Zone 3 — Normalized Output (right column, 14-row list):**
Unified 14-column schema: EventID · InterfaceID · SourceSystem · TargetSystem · Middleware · Pattern · Status · ErrorCode · ErrorText · RootCauseClass · Latency_ms · SessionID · RequestID · Timestamp

**Key callout (bottom of slide):**
> Zero hand-written parsers. Zero hallucinated data. LLM generates code; code runs deterministically.

---

## Part 3: Cost of Integration Failure (CoIF)

**Title:** CoIF — Turning Failure Events into Business Impact Scores

### Slide 3a: The Baseline Formula

**Formula (large, centered, highlighted box):**
```
CoIF = Failure Signal × Priority Weight × Process Weight × Cost Multiplier
```

**4 Factor Breakdown Cards (side-by-side, each a small card):**
- **Failure Signal** — Failed=1.0 · Retry=0.3 · Warning=0.5 · Success=0.0
- **Priority Weight** — Critical=100 · High=60 · Elevated=25 · Normal=5 · Low=2
- **Process Weight** — 0–100 from process_impact_weight.csv (Goods Receipt=100, Incident Sync=15)
- **Cost Multiplier** — Month-End Close=3.0× · Quarter-End Close=2.0× · Normal=1.0×

**Live Example Calculation (call-out box at bottom):**
> FAILED · Critical Payment Interface · Month-End Close:
> **1.0 × 100 × 90 × 3.0 = CoIF 27,000** → Immediate P1 escalation
> 
> vs. 500 failures on a low-priority CRM batch sync → CoIF 750 total → deprioritized

**Why this matters:** The TotalCoIF per interface = SUM of all event CoIF scores. The Health Map ranks every interface, process, and system by TotalCoIF — not by failure count.

### Slide 3b: Baseline vs ML Tradeoffs

**Comparison Table:**
| | Baseline Formula ✅ | ML Model 🚀 |
|:---|:---|:---|
| Cold start | Works day 1, no training data | Needs weeks of labelled history |
| Explainability | Every score is auditable by business users | Black-box — harder to justify |
| Adaptability | Static weights, manual tuning needed | Dynamic — adapts to patterns & seasonality |
| Cascades | Linear — misses knock-on amplification | GNN-based — models propagation |
| Prediction | Reactive — scores past failures only | Predictive — flags at-risk interfaces ahead of failure |

**Recommendation callout:** Hybrid approach — hardcoded formula as real-time auditable baseline + ML "Risk Signal" as a separate predictive layer on top.

---

## Part 4: What We Built — L1 Complete + L2 Stage 1 & 2

**Title:** Execution: L1 Fully Delivered, L2 Stage 1 + 2 Live

### Slide 4a: The 6-Page Live Dashboard

**Show as a dashboard screenshot mockup or icon grid with labels:**
| Page | What it does |
|------|-------------|
| 📊 Overview | KPI cards: total events, failure rate, top CoIF interface, active incidents |
| 🗺 Health Map | Interfaces ranked by TotalCoIF · CoIF formula explanation panel per row |
| 🔗 Dependency Graph | Interactive NetworkX/Plotly graph · SourceSystem → [Middleware] → TargetSystem nodes |
| 🚨 Incidents | Correlated incident clusters · timeline drill-down · affected interfaces |
| 🔍 Event Explorer | 13 filter dimensions · free-text search · per-event CoIF breakdown |
| 💬 Ask the Data | 8 question templates → deterministic pandas queries → evidence rows returned |

**Key technical detail:** Dependency graph now includes Middleware as explicit nodes (e.g., [Kafka], [ESB]) — not just edge labels — so bottleneck middleware is visually identifiable.

### Slide 4b: L2 Incident Correlation (Stage 1)

**Diagram — 3 Correlation Signals flowing into Union-Find:**
Show 3 input signals converging into a box labeled "Union-Find Clustering Algorithm":
1. **Temporal** — Same interface, events within ±5-minute window → merged
2. **Error Class** — Same ErrorCode + RootCauseClass across interfaces, within window → merged
3. **Dependency** — Events on graph-connected interfaces (SourceSystem→TargetSystem) within window → merged

**Output:** Discrete incident clusters, each with: timeline · affected interfaces · top error codes · total CoIF

**Note:** Restricting temporal correlation to the SAME interface prevents the "transitive chain" problem where all events collapse into one giant incident.

### Slide 4c: L2 RCA — Ask the Data (Stage 2)

**How it works (3-step flow):**
1. User types a natural-language question
2. Regex intent router matches to 1 of 8 question templates
3. Deterministic pandas query runs → returns actual event rows as evidence (no hallucination)

**8 Supported Question Types:**
- Which interface has the highest CoIF?
- What are the top failure root causes?
- Show me all failures on [interface]
- Which interfaces have SLA violations?
- What failed during month-end close?
- Which sessions have multiple failures?
- What is the failure rate by system?
- Show me the worst interfaces by process

---

## Part 5: Future Scope

**Title:** Roadmap — From Reactive to Autonomous

**Staircase diagram (4 ascending steps, left to right):**

| Step | Label | What it means |
|------|-------|---------------|
| ✅ Step 1 | Reactive — L1 | Live: CoIF Health Map · Log Normalization · NL Q&A |
| ✅ Step 2 | Correlated — L2 | Live: Incident clustering · Chronic vs. Event RCA |
| 🚀 Step 3 | Predictive — L3 | Build: GNN blast-radius risk score per interface pre-deployment |
| 🔮 Step 4 | Autonomous | Build: Closed-loop auto-routing + self-learning CoIF weights |

**3 Future Enhancements (cards):**
1. **L3 Blast-Radius Prediction** — GNNs on the dependency graph predict ranked downstream risk score for every proposed change event *before* it deploys.
2. **Closed-Loop Remediation** — Auto-route incidents to L1–L4 support queues via escalation_routing.csv. Human-in-loop approval gate for P1/Critical actions.
3. **Real-Time Streaming Ingest** — Replace batch CSV pipeline with Kafka consumer. CoIF scores recalculate within seconds of new events, not minutes.
