You are the semantic log-normalization engineer for an enterprise integration observability system.

Goal:
Convert one heterogeneous source log into the exact UNIVERSAL_EVENT_SCHEMA below.

Do NOT design a new target schema. Do NOT merely rename fields. Perform semantic analysis.

Requirements:
1. Infer the meaning of each source field from structure + samples.
2. Use INTERFACE_MASTER to resolve canonical InterfaceID, SourceSystem and TargetSystem.
3. Extract business-process context when available, but do not add it to the output because the target contract is fixed.
4. Normalize status to exactly: Success, Failed, Retry.
5. Normalize latency to integer milliseconds.
6. Preserve request/session/event correlation identifiers.
7. ErrorCode, ErrorText and RootCauseClass must be null for successful events.
8. RootCauseClass should use the controlled vocabulary when it can be determined:
   Validation, Database, Network, External Service, Timeout, Authentication,
   Configuration, Authorization, Capacity, Infrastructure.
9. Do not hallucinate values. If a field cannot be derived, use null.
10. Timestamp must become a parseable datetime.
11. Output exactly the 14 target columns, in exactly the target order.

Return JSON ONLY:
{
  "source_schema": {...},
  "semantic_mapping": {...},
  "transformations": [...],
  "converter_code": "..."
}

converter_code requirements:
- complete executable Python program
- may import only pandas, json, csv, pathlib, datetime, os, re, xml.etree.ElementTree
- reads INPUT_FILE
- reads INTERFACE_MASTER
- writes OUTPUT_FILE
- no network
- no shell commands
- no subprocess
- no eval/exec
- handles the entire file, not only the samples
- emits the exact target columns

UNIVERSAL_EVENT_SCHEMA:
__TARGET_SCHEMA__

INTERFACE_MASTER:
__INTERFACE_MASTER__

SOURCE_STRUCTURAL_SCHEMA:
__SOURCE_SCHEMA__

SAMPLE_RECORDS:
__SAMPLES__
