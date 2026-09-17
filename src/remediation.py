"""
remediation.py
--------------
L2 Stage 3 — Remediation Engine

For each incident (with RCA classification), this module:
    1. Generates a step-by-step remediation playbook
    2. Routes the incident to the correct team
    3. Flags incidents requiring human-in-loop review

All logic is deterministic and rule-based — keyed on ErrorCode pattern
and RootCauseClass from the actual event data.
"""

from __future__ import annotations

import re
from typing import List, Tuple
import pandas as pd


# ---------------------------------------------------------------------------
# Fix Playbook Catalogue
# ---------------------------------------------------------------------------
# Keyed by (ErrorCode substring pattern, RootCauseClass)
# Each entry: list of step strings
# More specific patterns checked first (longer match wins)

_PLAYBOOK: list[dict] = [
    # Timeout errors
    {
        "error_pattern": r"TIME",
        "root_cause":    "Timeout",
        "steps": [
            "1. Check network latency between SourceSystem and TargetSystem using `ping` / `traceroute`.",
            "2. Review gateway timeout configuration — increase if legitimate slow response.",
            "3. Inspect upstream service health dashboards for the TargetSystem.",
            "4. Enable retry with exponential backoff if not already configured.",
            "5. If timeout persists > 30 min, activate circuit breaker to prevent cascade.",
        ],
        "eta_min": 30,
        "auto_resolvable": False,
    },
    # Database errors
    {
        "error_pattern": r"DB",
        "root_cause":    "Database",
        "steps": [
            "1. Check database connection pool utilisation — if > 80%, scale pool size.",
            "2. Review slow query log for long-running transactions blocking connections.",
            "3. Restart the connection pool manager without full service restart.",
            "4. Verify DB host disk I/O and memory pressure metrics.",
            "5. If DB unreachable, initiate failover to read replica (read-only mode).",
            "6. Alert DBA team if connection count does not recover within 10 minutes.",
        ],
        "eta_min": 45,
        "auto_resolvable": False,
    },
    # Capacity errors
    {
        "error_pattern": r"CAP",
        "root_cause":    "Capacity",
        "steps": [
            "1. Check current queue depth on the affected middleware (MsgBus / ESB).",
            "2. Scale out queue consumers — add 2x consumer instances.",
            "3. Shed non-critical load by activating low-priority message throttling.",
            "4. Check upstream source (SourceSystem) for message storm — apply rate limiting.",
            "5. Monitor queue drain rate; if not draining in 15 min, escalate to Platform team.",
        ],
        "eta_min": 20,
        "auto_resolvable": True,
    },
    # Network errors
    {
        "error_pattern": r"NET",
        "root_cause":    "Network",
        "steps": [
            "1. Verify DNS resolution for TargetSystem hostname.",
            "2. Check firewall / security group rules for recent policy changes.",
            "3. Confirm VPN / private-link connectivity between source and target.",
            "4. Run `mtr` / `iperf` to identify packet loss or jitter.",
            "5. If cloud-hosted, check cloud provider status page for regional incidents.",
        ],
        "eta_min": 25,
        "auto_resolvable": False,
    },
    # Authorization errors
    {
        "error_pattern": r"AUTHZ|AUTH(?!R)",
        "root_cause":    "Authorization",
        "steps": [
            "1. Verify service account credentials have not expired — rotate if needed.",
            "2. Check RBAC / IAM policies for recent changes to the affected service role.",
            "3. Confirm OAuth token expiry settings match the integration's session length.",
            "4. Re-issue API keys / certificates if compromise is suspected.",
            "5. Audit authorisation logs for unusual patterns (potential breach indicator).",
        ],
        "eta_min": 20,
        "auto_resolvable": False,
    },
    # External service errors
    {
        "error_pattern": r"EXT|PO",
        "root_cause":    "ExternalService",
        "steps": [
            "1. Check the external provider's status page / incident feed.",
            "2. Activate fallback / secondary provider if configured.",
            "3. Enable circuit breaker to stop hammering the failing external endpoint.",
            "4. Notify business owner — SLA breach may require manual substitute action.",
            "5. If provider SLA is breached, initiate formal incident ticket with vendor.",
        ],
        "eta_min": 60,
        "auto_resolvable": False,
    },
    # Validation errors
    {
        "error_pattern": r"VAL|COMP",
        "root_cause":    "Validation",
        "steps": [
            "1. Identify the failing validation rule from the ErrorText field.",
            "2. Check whether a recent deployment changed the payload schema.",
            "3. Replay the failed message with corrected data if possible.",
            "4. Update schema validation rules if the upstream format has legitimately changed.",
            "5. Add message dead-letter queue to prevent blocking valid subsequent messages.",
        ],
        "eta_min": 40,
        "auto_resolvable": False,
    },
    # Infrastructure / machine errors
    {
        "error_pattern": r"MACHINE|INFRA",
        "root_cause":    "Infrastructure",
        "steps": [
            "1. Check host-level metrics: CPU, memory, disk I/O for the affected node.",
            "2. Attempt graceful controller restart: `systemctl restart <controller-service>`.",
            "3. If restart fails, trigger hardware diagnostic check.",
            "4. Shift workload to standby node if available.",
            "5. Escalate to Infrastructure/Hardware team for physical inspection if persistent.",
        ],
        "eta_min": 90,
        "auto_resolvable": False,
    },
    # Configuration errors
    {
        "error_pattern": r"CFG|CONFIG",
        "root_cause":    "Configuration",
        "steps": [
            "1. Compare current config to last known good configuration in version control.",
            "2. Identify the recent config change that caused the mismatch.",
            "3. Roll back configuration to previous version.",
            "4. Validate config against schema before redeploying.",
            "5. Add config-drift alerting to prevent future silent mismatches.",
        ],
        "eta_min": 20,
        "auto_resolvable": True,
    },
]

# Default fallback playbook
_DEFAULT_PLAYBOOK = {
    "steps": [
        "1. Review the ErrorText and RootCauseClass fields for the affected events.",
        "2. Check system health dashboards for SourceSystem and TargetSystem.",
        "3. Inspect recent deployment history for potential regression.",
        "4. Escalate to the Platform Engineering team if root cause is unclear.",
    ],
    "eta_min": 60,
    "auto_resolvable": False,
}


# ---------------------------------------------------------------------------
# Routing Table
# ---------------------------------------------------------------------------
# (ImpactTier, RCACategory) → (Team, EscalationLevel, Priority)
_ROUTING: dict[tuple, dict] = {
    ("CRITICAL", "CHRONIC"):       {"team": "Architecture + SRE Lead",      "escalation": "P1", "priority": 1},
    ("CRITICAL", "EVENT"):         {"team": "On-call SRE + Incident Commander", "escalation": "P1", "priority": 1},
    ("CRITICAL", "CHRONIC_EVENT"): {"team": "Architecture + SRE Lead",      "escalation": "P1", "priority": 1},
    ("HIGH",     "CHRONIC"):       {"team": "Platform Engineering + SRE",   "escalation": "P2", "priority": 2},
    ("HIGH",     "EVENT"):         {"team": "On-call SRE",                  "escalation": "P2", "priority": 2},
    ("HIGH",     "CHRONIC_EVENT"): {"team": "Platform Engineering + SRE",   "escalation": "P2", "priority": 2},
    ("MEDIUM",   "CHRONIC"):       {"team": "Platform Engineering",         "escalation": "P3", "priority": 3},
    ("MEDIUM",   "EVENT"):         {"team": "L1 Support",                   "escalation": "P3", "priority": 3},
    ("MEDIUM",   "CHRONIC_EVENT"): {"team": "Platform Engineering",         "escalation": "P3", "priority": 3},
    ("LOW",      "CHRONIC"):       {"team": "Platform Engineering",         "escalation": "P4", "priority": 4},
    ("LOW",      "EVENT"):         {"team": "L1 Support",                   "escalation": "P4", "priority": 4},
    ("LOW",      "CHRONIC_EVENT"): {"team": "L1 Support",                   "escalation": "P4", "priority": 4},
}

_DEFAULT_ROUTING = {"team": "L1 Support", "escalation": "P4", "priority": 4}


# ---------------------------------------------------------------------------
# Human-in-Loop triggers
# ---------------------------------------------------------------------------
def _requires_human_review(
    impact_tier: str,
    rca_category: str,
    confidence: float,
    blast_radius: float,
    n_systems: int,
) -> Tuple[bool, str]:
    reasons = []
    if impact_tier == "CRITICAL":
        reasons.append("CRITICAL impact tier")
    if confidence < 0.60:
        reasons.append(f"low RCA confidence ({int(confidence*100)}%)")
    if rca_category == "CHRONIC_EVENT":
        reasons.append("mixed chronic+event pattern is ambiguous")
    if isinstance(blast_radius, float) and blast_radius > 70:
        reasons.append(f"high blast radius ({blast_radius:.0f}/100)")
    if isinstance(n_systems, int) and n_systems >= 4:
        reasons.append(f"wide system blast ({n_systems} systems affected)")
    if reasons:
        return True, "; ".join(reasons)
    return False, ""


# ---------------------------------------------------------------------------
# Playbook lookup
# ---------------------------------------------------------------------------
def get_playbook_steps(error_code: str, root_cause_class: str) -> Tuple[List[str], int, bool]:
    """
    Returns (steps, eta_minutes, auto_resolvable) for a given error.
    Matches on error_code pattern first, then root_cause_class.
    """
    ec = str(error_code).upper()
    rc = str(root_cause_class).upper()

    for entry in _PLAYBOOK:
        pattern_match = re.search(entry["error_pattern"], ec)
        class_match   = rc == entry["root_cause"].upper()
        if pattern_match or class_match:
            return entry["steps"], entry["eta_min"], entry["auto_resolvable"]

    return _DEFAULT_PLAYBOOK["steps"], _DEFAULT_PLAYBOOK["eta_min"], _DEFAULT_PLAYBOOK["auto_resolvable"]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def generate_remediation(rca_df: pd.DataFrame) -> pd.DataFrame:
    """
    Stage 3: For every row in rca_df, produce remediation actions.

    Returns
    -------
    remediation_df — one row per incident, merged with rca_df fields.
    """
    if rca_df.empty:
        return pd.DataFrame()

    rows = []
    for _, row in rca_df.iterrows():
        impact_tier   = str(row.get("ImpactTier", "LOW"))
        rca_category  = str(row.get("RCACategory", "EVENT"))
        confidence    = float(row.get("ConfidenceScore", 0.5))
        blast_radius  = float(row.get("BlastRadius", 0.0))
        error_code    = str(row.get("PrimaryErrorCode", ""))
        root_cause    = str(row.get("PrimaryRootCauseClass", ""))
        n_systems     = len(row.get("AffectedSystems", [])) if isinstance(row.get("AffectedSystems"), list) else 1

        # Playbook
        steps, eta, auto_res = get_playbook_steps(error_code, root_cause)

        # Routing
        route = _ROUTING.get((impact_tier, rca_category), _DEFAULT_ROUTING)

        # Human-in-loop
        human_needed, human_reason = _requires_human_review(
            impact_tier, rca_category, confidence, blast_radius, n_systems
        )

        rows.append({
            "IncidentID":             row.get("IncidentID", ""),
            "ImpactTier":             impact_tier,
            "RCACategory":            rca_category,
            "AssignedTeam":           route["team"],
            "EscalationLevel":        route["escalation"],
            "Priority":               route["priority"],
            "PlaybookSteps":          steps,
            "EstimatedResolution_min": eta,
            "AutoResolvable":         auto_res,
            "HumanReviewRequired":    human_needed,
            "HumanReviewReason":      human_reason,
            "TotalCoIF":              row.get("TotalCoIF", 0),
            "BlastRadius":            blast_radius,
            "RootCauseInterface":     row.get("RootCauseInterface", ""),
            "RootCauseSystem":        row.get("RootCauseSystem", ""),
        })

    rem_df = pd.DataFrame(rows).sort_values("Priority").reset_index(drop=True)
    return rem_df
