# Self-Learning / Closed-Loop Architecture Design

## Overview

This document describes the **self-learning closed-loop** design for the Integration Health Monitor. The goal is to make the system improve automatically over time by learning from human reviewer decisions, successful remediations, and real-world MTTR data.

> Note: This is a design document — the components below are not yet built, but the architecture is production-ready and could be implemented incrementally.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│                    LIVE SYSTEM                           │
│                                                          │
│  Logs / Events ──► L1 Pipeline ──► L2 Pipeline          │
│                                         │                │
│                             Remediation Actions          │
│                                         │                │
│                          ┌──────────────▼───────────┐    │
│                          │  Human Reviewer UI        │    │
│                          │  (Accept / Reject / Edit) │    │
│                          └──────────────┬────────────┘    │
└─────────────────────────────────────────┼────────────────┘
                                          │ Feedback Events
                          ┌───────────────▼────────────────┐
                          │      Feedback Store             │
                          │  (append-only event log)        │
                          └───────────────┬────────────────┘
                                          │
          ┌───────────────────────────────▼───────────────────────────┐
          │                    Learning Subsystem                      │
          │                                                            │
          │  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐  │
          │  │ Feature Store │  │ Model Retrainer│  │ Drift Detector│  │
          │  │ (aggregated  │  │ (weekly batch) │  │ (daily check) │  │
          │  │  signals)    │  │               │  │               │  │
          │  └──────┬───────┘  └──────┬────────┘  └──────┬────────┘  │
          │         │                 │                   │            │
          │         └─────────────────▼───────────────────┘            │
          │                  Updated Models / Rules                    │
          └────────────────────────────────────────────────────────────┘
                                          │
                          ┌───────────────▼────────────────┐
                          │    Model Registry / Rule Store  │
                          │  (versioned, rollback-capable)  │
                          └────────────────────────────────┘
```

---

## Component Details

### 1. Feedback Ingestion

When a human reviewer acts on a flagged incident, one of three actions is recorded:

| Action | Meaning |
|---|---|
| **ACCEPT** | RCA + playbook were correct — incident was resolved as suggested |
| **REJECT** | RCA was wrong — reviewer provides the correct category + root cause |
| **MODIFY** | Playbook was partially correct — reviewer edits steps or routes to different team |

Each feedback event is written to the **Feedback Store** as an immutable append-only record:

```json
{
  "timestamp": "2026-09-18T10:32:00Z",
  "incident_id": "INC-0042",
  "reviewer_id": "sre-lead-01",
  "action": "REJECT",
  "predicted_category": "EVENT",
  "corrected_category": "CHRONIC",
  "predicted_root_cause": "IF_ORD_002",
  "corrected_root_cause": "IF_PAY_001",
  "actual_resolution_min": 120,
  "estimated_resolution_min": 30,
  "notes": "Payment gateway was root cause, not Order service"
}
```

---

### 2. Feature Store

The Feature Store aggregates signals from both the raw event stream and feedback events into ML-ready features per interface and per error code:

| Feature | Source |
|---|---|
| `recurrence_rate_7d` | Event log |
| `avg_coif_per_event` | CoIF pipeline |
| `p90_latency_ms` | Event log |
| `false_chronic_rate` | Feedback Store (REJECT where predicted=CHRONIC) |
| `actual_mttr_min` | Feedback Store (ACCEPT, actual resolution time) |
| `cascade_depth` | Dependency graph traversal |
| `sla_breach_rate` | Event log |

---

### 3. Model Retraining Loop

Two models are retrained on a **weekly batch cycle** (or triggered when feedback volume > 50 new records):

#### 3a. CoIF ML Model (already in L1)
- **Current**: `LinearRegression` trained on `coif_training_history_1.csv`
- **Closed-loop enhancement**: Retrain weekly using feedback-corrected CoIF values (where human says "this incident cost X, not the predicted Y")
- **Algorithm**: Keep `LinearRegression` but expand features with `recurrence_rate_7d` and `cascade_depth`

#### 3b. RCA Classifier
- **Current**: Statistical heuristics (rule-based thresholds)
- **Closed-loop enhancement**: Train a `RandomForestClassifier` on feedback-corrected labels
- **Features**: `recurrence_count`, `incident_duration_min`, `n_interfaces`, `n_systems`, `avg_coif`, `error_code_group`
- **Labels**: `CHRONIC` / `EVENT` / `CHRONIC_EVENT` (from ACCEPT/REJECT feedback)
- **Update cadence**: Weekly retrain, daily threshold adjustment

#### 3c. Playbook Effectiveness Score
- Not a model — a **lookup table** updated from feedback
- Each `(ErrorCode_group, RootCauseClass)` pair gets a `confidence_score` = `ACCEPT_count / (ACCEPT + REJECT count)`
- If confidence < 0.5, the playbook entry is flagged for manual review

---

### 4. Drift Detection

A **daily drift check** runs against the last 7 days of predictions vs. feedback:

| Metric | Alert Threshold |
|---|---|
| RCA Classification Accuracy | < 75% → retrain triggered |
| CoIF MAE drift | > 20% degradation vs. baseline → retrain triggered |
| Playbook Acceptance Rate | < 60% on any error group → flag for review |
| Human Review Queue depth | > 20 pending → notify SRE Lead |

Drift signals are written to a **monitoring dashboard** (separate from the health monitor).

---

### 5. A/B Testing of Fix Playbooks

When two plausible playbook variants exist for the same error class, the system runs an **A/B experiment**:

1. Randomly assign incoming incidents to Variant A or Variant B (50/50 split)
2. Record `actual_resolution_min` from feedback
3. After 30 incidents per variant: run a t-test on MTTR
4. Promote the winner; deprecate the loser
5. Log the experiment result to the Model Registry

---

### 6. Hallucination Rate (if LLM is introduced later)

If an LLM is added to generate narratives or playbooks in a future version:

- **Hallucination = a claim in the narrative that contradicts the actual event data**
- Measured by running a structured extraction on the LLM output and cross-checking against the `events_df` ground truth
- Target: hallucination rate < 2% on narrative factual claims
- Mitigation: All LLM prompts are grounded with event data context; output is post-processed against known fields

---

### 7. MTTD (Mean Time to Detect)

- Defined as: `min(Timestamp of first correlated event)` to `time the incident appears in the dashboard`
- Currently: near-real-time (bounded by Streamlit refresh interval, ~1 s with `st.rerun`)
- Closed-loop improvement: After feedback, incidents of the same `Signature` class are flagged earlier using a **pre-filter** that matches known chronic error patterns before full correlation runs

---

## Implementation Roadmap (not built yet)

| Phase | Component | Effort |
|---|---|---|
| Phase 1 | Feedback Store (simple SQLite append log) | 1 day |
| Phase 2 | Feature Store (pandas-based, CSV-backed) | 1 day |
| Phase 3 | RCA Classifier (RandomForest on feedback labels) | 2 days |
| Phase 4 | Drift detection + alerting | 1 day |
| Phase 5 | A/B playbook testing framework | 2 days |
| Phase 6 | CoIF model retraining pipeline | 1 day |

Total estimated effort: **~8 person-days** for a production-grade closed loop.
