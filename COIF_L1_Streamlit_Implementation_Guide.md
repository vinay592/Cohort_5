# Implementation Requirements: L1 Integration Health Monitoring + CoIF

## Objective

Build the **L1 pass-bar** of an AI-powered Integration Health Monitoring platform using the supplied CSV datasets.

The implementation must have a **Streamlit frontend** and should be runnable locally with a simple command.

The primary goal is to:

1. Load and validate the generated CSV datasets.
2. Normalize/correlate the integration telemetry through the relational keys.
3. Calculate a **Cost of Integration Failure (CoIF)** score exactly according to the formula below.
4. Produce a business-impact-ranked health map.
5. Detect/correlate incidents and failures.
6. Provide searchable/filterable evidence.
7. Provide basic evidence-grounded natural-language Q&A over the loaded data.
8. Keep the architecture clean enough that L2/L3 functionality can be added later.

---

# 1. L1 SCOPE

The reference challenge defines L1 as:

### Foundation + Core

- Ingest & normalize messy, multi-format logs.
- Searchable store + de-dup signatures.
- Health map ranked by CoIF.
- Incident correlation.
- Evidence-grounded NL Q&A.

Do NOT implement the full L2/L3 pipeline.

L2/L3 can be represented as extension points, but the working application should focus on L1.

---

# 2. INPUT DATASETS

The application will consume these CSV files:

```text
events.csv
interface_master.csv
priority_weight.csv
process_impact_weight.csv
business_calendar.csv
```

Additional files may exist later, such as:

```text
change_events.csv
escalation_routing.csv
```

but they are NOT required for the core L1 implementation.

If optional files are present, design the loader so they can be incorporated later without rewriting the architecture.

---

# 3. DATA MODEL

## 3.1 events.csv

Expected columns:

```text
EventID
InterfaceID
SourceSystem
TargetSystem
Middleware
Pattern
Status
ErrorCode
ErrorText
RootCauseClass
Latency_ms
SessionID
RequestID
Timestamp
```

Important:

- Every `InterfaceID` must exist in `interface_master.csv`.
- SourceSystem, TargetSystem, Middleware, and Pattern should agree with the referenced interface.
- Events represent failures/warnings in the current synthetic dataset.
- `Status` is expected to contain values such as `Failed` and `Warning`.
- ErrorCode should be present for every event.
- Timestamp should be parsed as datetime.

---

## 3.2 interface_master.csv

Expected columns:

```text
InterfaceID
SourceSystem
TargetSystem
Middleware
Pattern
BusinessProcess
Priority
Area
Criticality
SLA_ms
PriorityWeight
```

The six systems used by the current synthetic data are:

```text
ORD = Order System
MFG = Manufacturing System
PRC = Procuring System
ASM = Assembly System
DLV = Delivery System
PAY = Payment System
```

`InterfaceID` is the primary identifier for an integration interface.

---

## 3.3 priority_weight.csv

Schema:

```text
Priority
Weight
```

Expected mapping:

```text
Critical  -> 100
High      -> 60
Elevated  -> 25
Normal    -> 5
Low       -> 2
```

Do not hard-code the weight in the scoring logic if it can be read from this reference table.

Join:

```text
interface_master.Priority
    ->
priority_weight.Priority
    ->
priority_weight.Weight
```

---

## 3.4 process_impact_weight.csv

Schema:

```text
BusinessProcess
ProcessWeight
```

This table assigns the business-impact weight to each process.

Important:

- Every BusinessProcess used in interface_master must have a corresponding row.
- Do not treat all processes as equally important.
- ProcessWeight represents business impact, not technical failure percentage.

Examples:

```text
Payment Authorization -> very high
Order Creation        -> very high
Production Start      -> high
Shipment Dispatch     -> high
Assembly Completion   -> high
Routine Stock Update  -> lower
Informational Sync    -> lower
```

Join:

```text
interface_master.BusinessProcess
    ->
process_impact_weight.BusinessProcess
    ->
process_impact_weight.ProcessWeight
```

---

## 3.5 business_calendar.csv

Schema:

```text
WindowStart
WindowEnd
WindowType
CostMultiplier
```

Example:

```text
MEC     -> 2.0
QEC     -> 3.0
Normal  -> 1.0
```

The calendar multiplier represents the additional business cost/impact of failures during important close periods.

Join an event to the calendar using:

```text
event.Timestamp
    falls between
business_calendar.WindowStart and WindowEnd
```

If a timestamp does not fall into an explicit special window, use the applicable Normal multiplier.

---

# 4. CoIF FORMULA

The central scoring formula shown in the challenge material is:

```text
CoIF = Failure Signal × Priority Weight × Process-Impact Weight × Close-Calendar Multiplier
```

This formula must be implemented explicitly and transparently.

Do NOT replace it with an arbitrary ML score.

Do NOT normalize it into a percentage unless that is only for display.

The raw CoIF should remain available.

---

# 5. FAILURE SIGNAL

Implement a clearly defined `FailureSignal`.

For the current dataset, events are intentionally failures/warnings rather than ordinary successful telemetry.

Use a configurable mapping rather than burying the values throughout the code.

Recommended default:

```text
Failed  -> 1.0
Warning -> 0.5
```

The implementation should make this mapping easy to change.

For example:

```python
FAILURE_SIGNAL = {
    "Failed": 1.0,
    "Warning": 0.5,
}
```

If the dataset later contains:

```text
Success
Retry
```

the scoring layer should be able to support them without major refactoring.

For example:

```text
Success -> 0.0
Retry   -> configurable intermediate value
```

Do not silently treat unknown statuses as failures. Show a validation warning or handle them explicitly.

---

# 6. CoIF CALCULATION PIPELINE

The application should perform the following logical steps.

## Step 1: Load events

Load:

```text
events.csv
```

Parse:

```text
Timestamp
```

as a datetime.

---

## Step 2: Join interface metadata

Join events to interface_master on:

```text
events.InterfaceID = interface_master.InterfaceID
```

This provides:

```text
SourceSystem
TargetSystem
BusinessProcess
Priority
Area
Criticality
SLA_ms
PriorityWeight
```

Even if some of these fields are already present in events.csv, prefer the interface_master values as the authoritative metadata.

---

## Step 3: Join priority weight

Join:

```text
Priority -> priority_weight.Weight
```

Use the reference table as the source of truth.

Validate that:

```text
interface_master.PriorityWeight == priority_weight.Weight
```

when PriorityWeight is present.

---

## Step 4: Join process impact

Join:

```text
BusinessProcess -> ProcessWeight
```

from:

```text
process_impact_weight.csv
```

---

## Step 5: Determine calendar multiplier

For each event:

```text
Timestamp -> matching business calendar window
```

Retrieve:

```text
CostMultiplier
```

If multiple calendar windows overlap, handle the conflict explicitly and do not silently choose one.

---

## Step 6: Calculate FailureSignal

Based on Status.

Default:

```text
Failed  = 1.0
Warning = 0.5
```

---

## Step 7: Calculate CoIF

For each event:

```text
CoIF =
    FailureSignal
    × PriorityWeight
    × ProcessWeight
    × CostMultiplier
```

Store all intermediate values in the resulting dataframe.

Recommended derived columns:

```text
FailureSignal
PriorityWeight
ProcessWeight
CostMultiplier
CoIF
```

This is important for explainability.

---

# 7. EXAMPLE

Suppose:

```text
Status              = Failed
Priority            = Critical
PriorityWeight      = 100
BusinessProcess     = Payment Authorization
ProcessWeight       = 100
WindowType          = QEC
CostMultiplier      = 3.0
```

Then:

```text
FailureSignal = 1.0

CoIF =
1.0 × 100 × 100 × 3.0

CoIF = 30,000
```

A warning on a lower-impact interface might have a much lower score even if the number of warnings is high.

This is the core concept of the challenge:

> Severity is based on business impact, not merely failure percentage.

---

# 8. AGGREGATED HEALTH MAP

The Streamlit application must provide a **business-impact-ranked health map**.

At minimum, support aggregation at:

1. Interface level
2. Business Process level
3. System level

For example, calculate:

```text
Total CoIF
Event Count
Failed Count
Warning Count
Average Latency
SLA Violation Count
```

for each interface.

Then rank interfaces by:

```text
Total CoIF DESC
```

The highest-CoIF interfaces should appear first.

---

# 9. SYSTEM DEPENDENCY GRAPH

Because:

```text
SourceSystem -> TargetSystem
```

is available through interface_master, construct a directed dependency graph.

Example:

```text
ORD -> MFG
ORD -> PAY
PRC -> MFG
PRC -> ASM
MFG -> ASM
ASM -> DLV
PAY -> ORD
```

Use the event data to calculate the observed importance of each edge.

For each directed edge, show at least:

```text
SourceSystem
TargetSystem
EventCount
FailedCount
WarningCount
TotalCoIF
```

The graph should visually emphasize higher-impact dependencies.

Use a suitable Python graph library such as NetworkX.

Do not create fake edges that do not exist in interface_master.

---

# 10. INCIDENT CORRELATION

Implement a simple but useful L1 incident-correlation mechanism.

The objective is to group events that likely belong to the same incident.

Use multiple signals:

### Strong correlation

- Same RequestID
- Same SessionID

### Temporal correlation

Events occurring within a configurable time window, e.g.:

```text
±5 minutes
```

### Dependency correlation

Events occurring along connected interfaces:

```text
ORD -> MFG -> ASM -> DLV
```

### Error correlation

Similar:

```text
ErrorCode
RootCauseClass
SourceSystem
TargetSystem
```

can strengthen the relationship.

Do not claim that correlation proves causality.

Call it:

```text
Correlated Incident
```

or:

```text
Likely Incident Cluster
```

---

# 11. INCIDENT SUMMARY

For each correlated incident cluster, calculate:

```text
IncidentID
StartTime
EndTime
EventCount
AffectedInterfaces
AffectedSystems
PrimaryErrorCode
PrimaryRootCauseClass
TotalCoIF
MaxCoIF
```

Rank incidents by:

```text
TotalCoIF DESC
```

The UI should make it possible to click/select an incident and inspect the underlying events.

---

# 12. DE-DUPLICATION / SIGNATURES

L1 requires a searchable store with de-dup signatures.

Create a deterministic event signature from fields such as:

```text
InterfaceID
Status
ErrorCode
RootCauseClass
ErrorText
```

Normalize ErrorText before hashing:

- lowercase
- trim whitespace
- optionally remove volatile IDs/timestamps where appropriate

Generate something like:

```text
Signature
```

using SHA-256 or another deterministic hash.

Do NOT delete the original events.

Instead expose:

```text
Signature
DuplicateCount
```

so repeated occurrences can be identified.

The raw event count must remain intact for analytics.

---

# 13. SEARCHABLE EVENT STORE

The Streamlit UI should provide a searchable/filterable event explorer.

Filters should include:

```text
System
SourceSystem
TargetSystem
InterfaceID
BusinessProcess
Priority
Area
Status
ErrorCode
RootCauseClass
WindowType
Time range
Minimum CoIF
```

Display:

```text
EventID
Timestamp
InterfaceID
SourceSystem
TargetSystem
BusinessProcess
Status
ErrorCode
RootCauseClass
Latency_ms
CoIF
```

Allow the user to inspect an event and see the full evidence behind its CoIF score.

---

# 14. EVIDENCE-GROUNDED NL Q&A

Add a simple natural-language question interface in Streamlit.

The Q&A layer must answer from the loaded dataset rather than inventing facts.

Example questions:

```text
Which interface has the highest CoIF?

Why is payment authorization ranked above stock update?

Which systems are most impacted?

Which failures occurred during quarter-end close?

What are the top 5 incidents by business impact?

Which interface has the most SLA violations?

Show me all failures affecting ORD.

Why is IF_PAY_001 high priority?
```

Answers should cite/display the underlying rows or IDs used to produce the answer.

For example:

```text
IF_PAY_001 has the highest CoIF because:

- Status = Failed
- Priority = Critical
- Priority Weight = 100
- Business Process = Payment Authorization
- Process Weight = 100
- Calendar = QEC
- Calendar Multiplier = 3.0

CoIF = 1.0 × 100 × 100 × 3.0 = 30,000

Evidence:
Event IDs: EVT000010, ...
```

If an LLM is used, it must NOT be allowed to freely invent answers.

Prefer deterministic dataframe/query logic for numerical questions.

The LLM can be used for natural-language interpretation and explanation around retrieved evidence.

---

# 15. STREAMLIT FRONTEND

Create a clean dashboard.

Suggested navigation:

```text
Integration Health
├── Overview
├── Health Map
├── Dependency Graph
├── Incidents
├── Event Explorer
└── Ask the Data
```

## Overview

Show KPI cards:

```text
Total Events
Failed Events
Warning Events
Interfaces
Affected Systems
Total CoIF
SLA Violations
Correlated Incidents
```

Then show:

- Top interfaces by CoIF
- Top business processes by CoIF
- Top system dependencies
- Recent/high-impact incidents

---

# 16. HEALTH MAP

Display interfaces ranked by CoIF.

Suggested columns:

```text
Rank
InterfaceID
Source -> Target
BusinessProcess
Priority
ProcessWeight
FailureSignal
CalendarMultiplier
EventCount
FailedCount
SLA Violations
Total CoIF
```

Make CoIF visually prominent.

Allow sorting and filtering.

---

# 17. COIF EXPLANATION PANEL

When a user selects an interface, show the calculation.

Example:

```text
Interface: IF_PAY_001

Business Process:
Payment Authorization

Failure Signal:
1.0

Priority:
Critical

Priority Weight:
100

Process Impact:
100

Calendar:
QEC

Calendar Multiplier:
3.0

--------------------------------
CoIF
1.0 × 100 × 100 × 3.0
= 30,000
--------------------------------
```

Also show the events contributing to the score.

This is important for the demo because the judges need to see that the score is explainable.

---

# 18. DEPENDENCY GRAPH UI

Show:

```text
Source -> Target
```

as directed edges.

Node/edge information should be based only on actual data.

Allow selecting an edge to display:

```text
Event Count
Failed Count
Warning Count
Total CoIF
Top Error Codes
Affected Interfaces
```

A high-CoIF edge should be visually distinguishable from a low-CoIF edge.

---

# 19. INCIDENT UI

Display incidents ranked by:

```text
Total CoIF
```

For each incident show:

```text
Incident ID
Time window
Systems affected
Interfaces affected
Event count
Top error
Root cause class
Total CoIF
```

Selecting an incident should reveal its event timeline.

---

# 20. DATA VALIDATION

On application startup, validate all relationships.

At minimum:

### Referential integrity

```text
events.InterfaceID
    exists in
interface_master.InterfaceID
```

### Priority integrity

```text
interface_master.Priority
    exists in
priority_weight.Priority
```

### Process integrity

```text
interface_master.BusinessProcess
    exists in
process_impact_weight.BusinessProcess
```

### Calendar integrity

Every event timestamp must map to a valid calendar multiplier.

### System integrity

SourceSystem and TargetSystem must use known system codes.

### Status integrity

Current dataset:

```text
Failed
Warning
```

Unknown statuses should be surfaced.

Do not silently discard invalid rows.

Display a validation status in the Streamlit UI.

---

# 21. ARCHITECTURE

Keep the implementation modular.

Suggested structure:

```text
project/
│
├── app.py
│
├── data/
│   ├── events.csv
│   ├── interface_master.csv
│   ├── priority_weight.csv
│   ├── process_impact_weight.csv
│   └── business_calendar.csv
│
├── src/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── validation.py
│   ├── normalization.py
│   ├── coif.py
│   ├── incidents.py
│   ├── graph.py
│   ├── signatures.py
│   ├── queries.py
│   └── ui_helpers.py
│
├── requirements.txt
└── README.md
```

The exact structure can differ, but keep:

- data loading
- validation
- scoring
- correlation
- graph construction
- UI

separated.

---

# 22. PERFORMANCE

3,000 events is small.

Do NOT over-engineer this with distributed infrastructure.

Pandas is sufficient.

Load data once and use Streamlit caching:

```python
st.cache_data
```

Avoid repeatedly reading the CSV files for every UI interaction.

---

# 23. TECHNOLOGY

Use:

```text
Python 3.x
Pandas
Streamlit
NetworkX
Plotly
```

Other lightweight packages may be used if genuinely useful.

Do not introduce unnecessary infrastructure such as Kafka, Spark, databases, Kubernetes, etc.

The demo should run locally.

---

# 24. REQUIREMENTS.TXT

Create a requirements.txt containing the required dependencies.

At minimum:

```text
streamlit
pandas
numpy
networkx
plotly
```

Add other dependencies only when needed.

---

# 25. README

Create a README explaining:

1. What the application does.
2. Dataset structure.
3. CoIF formula.
4. How the score is calculated.
5. How incident correlation works.
6. How to run the application.
7. How to use the Streamlit dashboard.
8. Example questions for the Q&A interface.

Running should be as simple as:

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

# 26. IMPORTANT BUSINESS SEMANTICS

Do not reduce the application to:

```text
failure_count / total_count
```

The challenge explicitly wants:

```text
BUSINESS IMPACT
```

The CoIF score must reflect:

```text
Failure Signal
        ×
Priority Weight
        ×
Process Impact Weight
        ×
Close-Calendar Multiplier
```

Therefore:

A low-frequency failure on a Critical financial interface during quarter-end can outrank a high-frequency warning on a low-priority operational interface.

For example:

```text
Payment Authorization
Critical = 100
Process Impact = 100
QEC = 3.0
Failure = 1.0

CoIF = 30,000
```

while:

```text
Routine Stock Update
Elevated = 25
Process Impact = 40
Normal = 1.0
Warning = 0.5

CoIF = 500
```

The dashboard should make this business-impact distinction obvious.

---

# 27. ACCEPTANCE CRITERIA

The implementation is complete only when all of the following work:

### Data

- [ ] All five CSV files load successfully.
- [ ] Referential integrity is validated.
- [ ] Invalid/missing relationships are surfaced.

### CoIF

- [ ] CoIF uses exactly the specified formula.
- [ ] FailureSignal is explicit.
- [ ] PriorityWeight comes from priority_weight.csv.
- [ ] ProcessWeight comes from process_impact_weight.csv.
- [ ] Calendar multiplier comes from business_calendar.csv.
- [ ] Intermediate score components are visible.
- [ ] Raw CoIF is preserved.

### Health map

- [ ] Interfaces can be ranked by CoIF.
- [ ] Business processes can be ranked by CoIF.
- [ ] Systems can be ranked by CoIF.

### Dependency graph

- [ ] Directed graph is constructed from SourceSystem -> TargetSystem.
- [ ] No fabricated dependencies.
- [ ] Edge impact can be inspected.

### Incidents

- [ ] Related events can be clustered.
- [ ] Incident clusters show evidence.
- [ ] Incidents can be ranked by CoIF.

### Search

- [ ] Events are searchable/filterable.
- [ ] Error codes and interfaces can be queried.
- [ ] CoIF can be filtered.

### Q&A

- [ ] Numerical answers come from actual data.
- [ ] Answers show supporting evidence.
- [ ] The system does not hallucinate unsupported facts.

### Frontend

- [ ] Streamlit application runs with one command.
- [ ] Dashboard is understandable without reading the source code.
- [ ] CoIF calculation is explainable from the UI.

---

# 28. DO NOT IMPLEMENT YET

Do not spend significant time implementing:

```text
L2 RCA
L2 remediation
L3 blast-radius prediction
L3 ground-truth precision/recall
Self-learning loops
Model training
Production deployment infrastructure
```

These are future extensions.

The priority is a polished, reliable **L1 implementation** that demonstrates:

```text
MESSY EVENTS
    ↓
NORMALIZED DATA
    ↓
BUSINESS-AWARE SCORING
    ↓
CoIF HEALTH MAP
    ↓
DEPENDENCY GRAPH
    ↓
INCIDENT CORRELATION
    ↓
EVIDENCE-GROUNDED Q&A
```

# 29. FINAL DELIVERABLE

Produce a complete runnable project, not pseudocode.

The final project should include:

```text
app.py
src/*.py
requirements.txt
README.md
```

and should work against the supplied CSV files.

The implementation should prioritize:

1. Correctness
2. Explainability
3. Business-impact scoring
4. Referential consistency
5. Clean Streamlit UX
6. Simple architecture
7. Easy extension to L2/L3
