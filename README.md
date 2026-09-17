# L1 Integration Health Monitoring — CoIF Platform

> **Micron Challenge — L1 pass-bar**  
> A Streamlit dashboard that ingests integration telemetry, computes business-impact scores (CoIF), and surfaces ranked health maps, incident clusters, and evidence-grounded Q&A.

---

## What It Does

The platform transforms raw integration events into a **business-impact-ranked view** through the **Cost of Integration Failure (CoIF)** formula:

```
CoIF = Failure Signal × Priority Weight × Process-Impact Weight × Close-Calendar Multiplier
```

A single failure on a Critical financial interface during quarter-end close can have a CoIF of **30,000**, while hundreds of warnings on a low-priority sync interface may accumulate to just **500** — because **severity is business impact, not failure count**.

---

## Dataset Structure

| File | Description |
|------|-------------|
| `events.csv` | Raw integration failure/warning events |
| `interface_master.csv` | Interface metadata (systems, priority, business process, SLA) |
| `priority_weight.csv` | Priority → numeric weight mapping |
| `process_impact_weight.csv` | BusinessProcess → process weight mapping |
| `business_calendar.csv` | Calendar windows (MEC, QEC) with cost multipliers |

All files go in the `data/` directory.

---

## CoIF Formula

```
CoIF = FailureSignal × PriorityWeight × ProcessWeight × CostMultiplier
```

| Component | Source | Example |
|-----------|--------|---------|
| `FailureSignal` | Configurable map: Failed=1.0, Warning=0.5 | 1.0 |
| `PriorityWeight` | `priority_weight.csv` | Critical → 100 |
| `ProcessWeight` | `process_impact_weight.csv` | Payment Authorization → 100 |
| `CostMultiplier` | `business_calendar.csv` (timestamp interval) | QEC → 3.0 |

**Example:**
```
Status = Failed, Priority = Critical, BusinessProcess = Payment Authorization, WindowType = QEC

CoIF = 1.0 × 100 × 100 × 3.0 = 30,000
```

All intermediate components are stored per event for full explainability.

---

## How Incident Correlation Works

Events are grouped into **Likely Incident Clusters** using four signals:

1. **Strong correlation** — Same `RequestID` or `SessionID`
2. **Temporal correlation** — Events within ±5 minutes of each other
3. **Dependency correlation** — Events on directly connected interfaces (e.g. ORD→MFG→ASM→DLV)
4. **Error correlation** — Same `ErrorCode + RootCauseClass` within the time window

A **Union-Find (disjoint-set)** algorithm merges events connected by any of these signals. Incidents are ranked by **Total CoIF** (business impact).

---

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the dashboard
streamlit run app.py
```

The app loads all CSVs from the `data/` directory automatically.

---

## Dashboard Pages

| Page | Description |
|------|-------------|
| **Overview** | KPI cards, top interfaces/processes/incidents, event timeline |
| **Health Map** | Interface/process/system tables ranked by CoIF; CoIF explanation panel |
| **Dependency Graph** | Directed system graph with CoIF-encoded edge weights |
| **Incidents** | Correlated incident clusters with drill-down to event timelines |
| **Event Explorer** | Filterable event store with signature de-duplication |
| **Ask the Data** | Evidence-grounded NL Q&A with supporting data rows |

---

## Example Q&A Questions

Try these in the **Ask the Data** page:

- *Which interface has the highest CoIF?*
- *Top 5 incidents by business impact*
- *Which failures occurred during QEC?*
- *Which systems are most impacted?*
- *Which interface has the most SLA violations?*
- *Show me all failures affecting PAY*
- *Why is IF_PAY_001 high priority?*
- *Which failures occurred during MEC?*

---

## Architecture

```
app.py                      # Streamlit entry point
src/
  data_loader.py            # Load + cache all CSVs
  validation.py             # Referential integrity checks
  normalization.py          # Join tables, resolve metadata
  coif.py                   # CoIF formula + aggregations
  signatures.py             # SHA-256 event de-duplication
  incidents.py              # Incident correlation engine
  graph.py                  # NetworkX dependency graph + Plotly render
  queries.py                # Deterministic NL Q&A engine
  ui_helpers.py             # Plotly chart helpers + dark theme CSS
data/
  events.csv
  interface_master.csv
  priority_weight.csv
  process_impact_weight.csv
  business_calendar.csv
requirements.txt
README.md
```

---

## L2/L3 Extension Points

The architecture is designed for easy extension:
- `src/data_loader.py` — already handles optional `change_events.csv`, `escalation_routing.csv`
- `src/coif.py` — `FAILURE_SIGNAL` dict is configurable, add new statuses without refactoring
- `src/incidents.py` — correlation window is a top-level constant; additional signals can be added
- `src/queries.py` — query registry is a simple pattern-match dict; new templates slot in cleanly
