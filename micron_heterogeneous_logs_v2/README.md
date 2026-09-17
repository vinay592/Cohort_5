# Micron Hackathon — Heterogeneous Enterprise Log Normalization

## Final landscape

Six enterprise systems:
1. SAP ERP — Product Planning, Quality Management, Procurement, Finance
2. Oracle Supply Chain — Supply Chain Management, Inventory Management, Warehouse Management, Order Management
3. MES — Production Execution, Equipment Management, Process Control, Yield Management
4. PLM — Product Design, Change Management, Document Management, Configuration Management
5. CRM — Sales Management, Customer Management, Order Management, Demand Management
6. HCM — Workforce Management, Payroll, Talent Management, Time Management

There are 28 business-driven interfaces in `config/landscape.json`.

## Source telemetry

Each system has its OWN deliberately incompatible log format:

| System | File | Format |
|---|---|---|
| SAP ERP | `sap_erp.log` | pipe-delimited operational log + embedded key/value details |
| Oracle SCM | `oracle_scm.jsonl` | nested JSON Lines |
| MES | `mes_runtime.log` | double-pipe key/value runtime log + packed context |
| PLM | `plm_events.xml` | XML event records/attributes |
| CRM | `crm_audit.txt` | semicolon-delimited audit text |
| HCM | `hcm_activity.csv` | CSV with different names, codes and units |

This is intentional. The source schemas do NOT match the target schema.

## Target

Every source is converted to exactly:

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

This mirrors the `events.csv` structure in the project material.

## Run it

Install:

    pip install -r requirements.txt

Generate 6 heterogeneous logs:

    python generate_heterogeneous_logs.py --rows 6000

Local end-to-end test without an LLM:

    python normalize_logs_with_llm.py --offline-demo
    python scripts/validate_and_merge.py

LLM-assisted mode with OpenCode:

    python normalize_logs_with_llm.py --execute-generated-code

or:

    LLM_CLI=lingling python normalize_logs_with_llm.py --execute-generated-code

## What the LLM actually does

For each file, the orchestrator:
1. Extracts a structural schema.
2. Samples representative records.
3. Supplies the structural schema, samples, universal target schema and interface master to the LLM.
4. Requests semantic field mapping and a small executable converter.
5. Saves the LLM response as an artifact.
6. Runs the generated converter in a separate subprocess with a timeout.
7. Validates the resulting 14-column contract.
8. Writes a normalized CSV.

The LLM is therefore doing semantic normalization, not merely column renaming.

## Why the generated logs are suitable for the next stages

The generator deliberately creates:
- success, retry and failure events;
- 10 controlled root-cause classes;
- repeated failures across interfaces;
- realistic latency variation and SLA violations;
- request/session/event identifiers;
- 28 business interfaces;
- 7 days of timestamps;
- enough volume to reveal chronic patterns.

That lets the next stages perform:
- failure-signal calculation,
- incident correlation,
- interface health maps,
- business-process impact,
- COIF prioritization,
- grounded natural-language Q&A.

## Security

Treat LLM-generated code as untrusted. This prototype runs it as a separate process with a timeout. For production, execute generated converters inside a locked-down container with network disabled and strict filesystem permissions.
