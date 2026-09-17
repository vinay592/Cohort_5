#!/usr/bin/env python3
"""
Generate two consistent synthetic CSV datasets modelling an enterprise
integration environment:

    interface_master.csv  - ~15 integration interfaces between six systems
    events.csv            - 3,000 problem events (Failed / Warning) that
                            reference the interfaces as a foreign key

The data is designed so that a directed dependency graph
(SourceSystem -> TargetSystem) can be reconstructed later from the events by
joining events.InterfaceID -> interface_master.

Usage:
    python generate_data.py            # deterministic (default seed)
    python generate_data.py --seed 7   # different deterministic run

Only the standard library is used.
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

SYSTEMS = ["ORD", "MFG", "PRC", "ASM", "DLV", "PAY"]

N_EVENTS = 3000
N_DAYS = 7

# Root-cause classes and the failure "families" they belong to. Some classes
# tend to produce elevated latency (see LATENCY_HEAVY).
ROOT_CAUSES = [
    "Database",
    "Network",
    "Infrastructure",
    "Configuration",
    "Authentication",
    "Authorization",
    "ExternalService",
    "Timeout",
    "Validation",
    "Capacity",
]
LATENCY_HEAVY = {"Timeout", "Network", "Database", "ExternalService"}

# SLA budgets keyed by (Priority, Criticality). Values are milliseconds.
SLA_TABLE = {
    ("Critical", "P1"): 800,
    ("Critical", "P2"): 1200,
    ("High", "P1"): 1000,
    ("High", "P2"): 1500,
    ("High", "P3"): 2000,
    ("Medium", "P2"): 2500,
    ("Medium", "P3"): 3000,
    ("Low", "P3"): 5000,
}


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #


@dataclass
class Interface:
    InterfaceID: str
    SourceSystem: str
    TargetSystem: str
    Middleware: str
    Pattern: str
    BusinessProcess: str
    Priority: str
    Area: str
    Criticality: str
    SLA_ms: int


@dataclass
class Event:
    EventID: str
    InterfaceID: str
    SourceSystem: str
    TargetSystem: str
    Middleware: str
    Pattern: str
    Status: str
    ErrorCode: str
    ErrorText: str
    RootCauseClass: str
    Latency_ms: int
    SessionID: str
    RequestID: str
    Timestamp: str


# --------------------------------------------------------------------------- #
# Interface master generation
# --------------------------------------------------------------------------- #

# Fixed, hand-authored set of ~15 interconnected interfaces so that the
# dependency chain is realistic and stable. Each tuple is:
#   (src, tgt, middleware, pattern, business_process, priority,
#    area, criticality)
INTERFACE_SPECS = [
    ("ORD", "MFG", "MsgBus", "Async", "order creation", "Critical", "Sales", "P1"),
    ("ORD", "PAY", "API", "REST", "payment request", "Critical", "Finance", "P1"),
    ("ORD", "PRC", "ESB", "SOAP", "order validation", "High", "Sales", "P2"),
    ("PAY", "ORD", "API", "REST", "payment authorization", "Critical", "Finance", "P1"),
    ("PRC", "MFG", "ESB", "SOAP", "purchase order creation", "High", "Procurement", "P2"),
    ("PRC", "ASM", "MsgBus", "Async", "material receipt", "High", "Procurement", "P2"),
    ("MFG", "ASM", "MsgBus", "Async", "production start", "High", "Manufacturing", "P2"),
    ("MFG", "PRC", "API", "REST", "material request", "Medium", "Manufacturing", "P3"),
    ("ASM", "DLV", "ESB", "Batch", "assembly completion", "High", "Assembly", "P2"),
    ("ASM", "MFG", "API", "REST", "quality check", "Medium", "Assembly", "P2"),
    ("DLV", "ORD", "API", "REST", "shipment dispatch", "High", "Logistics", "P2"),
    ("DLV", "PAY", "MsgBus", "Async", "delivery confirmation", "Medium", "Logistics", "P3"),
    ("MFG", "DLV", "ESB", "CDC", "assembly start", "Medium", "Manufacturing", "P3"),
    ("PAY", "PRC", "API", "REST", "invoice settlement", "Medium", "Finance", "P3"),
    ("ORD", "DLV", "ESB", "Batch", "order fulfilment", "Low", "Sales", "P3"),
]


def build_interfaces() -> list[Interface]:
    interfaces: list[Interface] = []
    counters: dict[str, int] = {s: 0 for s in SYSTEMS}
    for src, tgt, mw, pattern, process, priority, area, crit in INTERFACE_SPECS:
        counters[src] += 1
        iface_id = f"IF_{src}_{counters[src]:03d}"
        sla = SLA_TABLE.get((priority, crit))
        if sla is None:
            # Fallback so the table is always consistent.
            sla = {"Critical": 1000, "High": 1800, "Medium": 3000, "Low": 5000}[priority]
        interfaces.append(
            Interface(
                InterfaceID=iface_id,
                SourceSystem=src,
                TargetSystem=tgt,
                Middleware=mw,
                Pattern=pattern,
                BusinessProcess=process,
                Priority=priority,
                Area=area,
                Criticality=crit,
                SLA_ms=sla,
            )
        )
    return interfaces


# --------------------------------------------------------------------------- #
# Error catalogue
# --------------------------------------------------------------------------- #

# Map a root-cause class to (error-code fragment, human text template).
ROOT_CAUSE_ERRORS = {
    "Database": ("DB", "Database {sys} operation failed: connection pool exhausted"),
    "Network": ("NET", "Network error contacting {tgt}: connection reset"),
    "Infrastructure": ("INFRA", "Infrastructure fault on {sys}: node unavailable"),
    "Configuration": ("CFG", "Configuration mismatch on {sys} endpoint"),
    "Authentication": ("AUTH", "Authentication rejected between {sys} and {tgt}"),
    "Authorization": ("AUTHZ", "Authorization denied for {sys}->{tgt} request"),
    "ExternalService": ("EXT", "External service {tgt} returned an error response"),
    "Timeout": ("TMO", "Timeout waiting for {tgt} to respond"),
    "Validation": ("VAL", "Validation failed for payload from {sys}"),
    "Capacity": ("CAP", "Capacity limit reached on {sys}: request throttled"),
}


def make_error(interface: Interface, root_cause: str, status: str, seq: int) -> tuple[str, str]:
    frag, template = ROOT_CAUSE_ERRORS[root_cause]
    code = f"{interface.SourceSystem}_{frag}_{seq % 900 + 1:03d}"
    text = template.format(sys=interface.SourceSystem, tgt=interface.TargetSystem)
    if status == "Warning":
        text = "WARNING: " + text + " (degraded, retrying)"
    return code, text


# --------------------------------------------------------------------------- #
# Latency
# --------------------------------------------------------------------------- #


def make_latency(interface: Interface, root_cause: str, status: str, rng: random.Random) -> int:
    sla = interface.SLA_ms
    if root_cause in LATENCY_HEAVY:
        # Heavy classes: centred high, frequently blowing past SLA.
        base = rng.uniform(0.6, 2.5) * sla
    elif status == "Failed":
        base = rng.uniform(0.4, 1.4) * sla
    else:  # Warning
        base = rng.uniform(0.3, 1.1) * sla
    # Guarantee some outright SLA violations regardless of class.
    if rng.random() < 0.15:
        base = rng.uniform(1.2, 3.0) * sla
    return max(1, int(base))


# --------------------------------------------------------------------------- #
# Timestamps (business-hours weighted over 7 days)
# --------------------------------------------------------------------------- #


def hour_weight(hour: int) -> float:
    if 9 <= hour <= 17:
        return 6.0          # business hours
    if 6 <= hour <= 8 or 18 <= hour <= 21:
        return 2.0          # shoulder
    return 0.4              # overnight


def random_timestamp(start: datetime, rng: random.Random) -> datetime:
    day = rng.randint(0, N_DAYS - 1)
    # Weighted hour selection.
    hours = list(range(24))
    weights = [hour_weight(h) for h in hours]
    hour = rng.choices(hours, weights=weights, k=1)[0]
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    return start + timedelta(days=day, hours=hour, minutes=minute, seconds=second)


# --------------------------------------------------------------------------- #
# Event generation with failure propagation
# --------------------------------------------------------------------------- #

# Downstream dependency map: which interfaces plausibly react when a given
# system's outgoing interface fails. Keyed by system, gives target systems
# whose interfaces may cascade.
DOWNSTREAM = {
    "ORD": ["MFG", "PAY", "DLV"],
    "PAY": ["ORD", "PRC"],
    "PRC": ["MFG", "ASM"],
    "MFG": ["ASM", "DLV"],
    "ASM": ["DLV", "MFG"],
    "DLV": ["ORD", "PAY"],
}


def generate_events(
    interfaces: list[Interface], start: datetime, rng: random.Random
) -> list[Event]:
    by_source: dict[str, list[Interface]] = {}
    for iface in interfaces:
        by_source.setdefault(iface.SourceSystem, []).append(iface)

    # Weight interfaces so important dependencies get many observations.
    weight = {
        "Critical": 5.0,
        "High": 3.0,
        "Medium": 1.5,
        "Low": 0.7,
    }
    iface_weights = [weight[i.Priority] for i in interfaces]

    events: list[Event] = []
    event_seq = 0
    request_seq = 0

    def next_ids() -> tuple[str, str]:
        nonlocal event_seq, request_seq
        event_seq += 1
        request_seq += 1
        return f"EVT_{event_seq:06d}", f"REQ_{request_seq:08d}"

    def emit(
        interface: Interface, ts: datetime, session_id: str, forced_status: str | None = None
    ) -> None:
        status = forced_status or ("Failed" if rng.random() < 0.60 else "Warning")
        root_cause = rng.choice(ROOT_CAUSES)
        eid, rid = next_ids()
        code, text = make_error(interface, root_cause, status, event_seq)
        latency = make_latency(interface, root_cause, status, rng)
        events.append(
            Event(
                EventID=eid,
                InterfaceID=interface.InterfaceID,
                SourceSystem=interface.SourceSystem,
                TargetSystem=interface.TargetSystem,
                Middleware=interface.Middleware,
                Pattern=interface.Pattern,
                Status=status,
                ErrorCode=code,
                ErrorText=text,
                RootCauseClass=root_cause,
                Latency_ms=latency,
                SessionID=session_id,
                RequestID=rid,
                Timestamp=ts.strftime("%Y-%m-%d %H:%M:%S"),
            )
        )

    session_seq = 0
    while len(events) < N_EVENTS:
        session_seq += 1
        session_id = f"SES_{session_seq:06d}"
        base_ts = random_timestamp(start, rng)

        # Primary event on a weighted-random interface.
        primary = rng.choices(interfaces, weights=iface_weights, k=1)[0]
        emit(primary, base_ts, session_id)
        if len(events) >= N_EVENTS:
            break

        # Failure propagation: with some probability, cascade to downstream
        # interfaces within the same session and a related timeframe.
        if rng.random() < 0.35:
            downstream_systems = DOWNSTREAM.get(primary.TargetSystem, [])
            candidates = [
                i
                for i in interfaces
                if i.SourceSystem == primary.TargetSystem
                and i.TargetSystem in downstream_systems
            ]
            rng.shuffle(candidates)
            for iface in candidates[: rng.randint(1, 2)]:
                if len(events) >= N_EVENTS:
                    break
                cascade_ts = base_ts + timedelta(seconds=rng.randint(2, 300))
                # Cascaded events lean toward warnings.
                forced = "Warning" if rng.random() < 0.55 else "Failed"
                emit(iface, cascade_ts, session_id, forced_status=forced)

    return events[:N_EVENTS]


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def validate(
    interfaces: list[Interface], events: list[Event], start: datetime, end: datetime
) -> None:
    iface_map = {i.InterfaceID: i for i in interfaces}

    assert len(interfaces) == 15, f"expected 15 interfaces, got {len(interfaces)}"
    assert len(events) == N_EVENTS, f"expected {N_EVENTS} events, got {len(events)}"

    seen_events: set[str] = set()
    seen_requests: set[str] = set()
    iface_counts: dict[str, int] = {}

    for e in events:
        assert e.InterfaceID, "InterfaceID is null"
        assert e.InterfaceID in iface_map, f"unknown InterfaceID {e.InterfaceID}"
        iface = iface_map[e.InterfaceID]
        assert e.SourceSystem == iface.SourceSystem, "SourceSystem mismatch"
        assert e.TargetSystem == iface.TargetSystem, "TargetSystem mismatch"
        assert e.Middleware == iface.Middleware, "Middleware mismatch"
        assert e.Pattern == iface.Pattern, "Pattern mismatch"
        assert e.EventID not in seen_events, f"duplicate EventID {e.EventID}"
        assert e.RequestID not in seen_requests, f"duplicate RequestID {e.RequestID}"
        seen_events.add(e.EventID)
        seen_requests.add(e.RequestID)
        assert e.Status in ("Failed", "Warning"), f"bad Status {e.Status}"
        assert e.ErrorCode, "ErrorCode is null"
        assert e.Latency_ms > 0, "Latency_ms not positive"
        ts = datetime.strptime(e.Timestamp, "%Y-%m-%d %H:%M:%S")
        assert start <= ts <= end, f"timestamp {ts} out of range"
        iface_counts[e.InterfaceID] = iface_counts.get(e.InterfaceID, 0) + 1

    # Every interface must be observed multiple times.
    for iface in interfaces:
        assert iface_counts.get(iface.InterfaceID, 0) >= 2, (
            f"interface {iface.InterfaceID} has too few events"
        )

    # Dependency graph must contain multiple connected paths.
    edges = {(i.SourceSystem, i.TargetSystem) for i in interfaces}
    assert len(edges) >= 5, "too few unique dependencies"
    # Confirm at least one multi-hop path exists, e.g. PRC->MFG->ASM->DLV.
    adj: dict[str, set[str]] = {}
    for s, t in edges:
        adj.setdefault(s, set()).add(t)
    assert "MFG" in adj.get("PRC", set()), "missing PRC->MFG"
    assert "ASM" in adj.get("MFG", set()), "missing MFG->ASM"
    assert "DLV" in adj.get("ASM", set()), "missing ASM->DLV"


# --------------------------------------------------------------------------- #
# CSV writing
# --------------------------------------------------------------------------- #


def write_csv(path: str, rows: list, fieldnames: list[str]) -> None:
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic integration data.")
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    start = datetime(2026, 9, 10, 0, 0, 0)
    end = start + timedelta(days=N_DAYS) - timedelta(seconds=1)

    interfaces = build_interfaces()
    events = generate_events(interfaces, start, rng)

    validate(interfaces, events, start, end)

    write_csv(
        "interface_master.csv",
        interfaces,
        [
            "InterfaceID", "SourceSystem", "TargetSystem", "Middleware", "Pattern",
            "BusinessProcess", "Priority", "Area", "Criticality", "SLA_ms",
        ],
    )
    write_csv(
        "events.csv",
        events,
        [
            "EventID", "InterfaceID", "SourceSystem", "TargetSystem", "Middleware",
            "Pattern", "Status", "ErrorCode", "ErrorText", "RootCauseClass",
            "Latency_ms", "SessionID", "RequestID", "Timestamp",
        ],
    )

    # Summary
    iface_map = {i.InterfaceID: i for i in interfaces}
    failed = sum(1 for e in events if e.Status == "Failed")
    warning = sum(1 for e in events if e.Status == "Warning")
    deps = {(e.SourceSystem, e.TargetSystem) for e in events}
    sla_violating_ifaces = {
        e.InterfaceID for e in events if e.Latency_ms > iface_map[e.InterfaceID].SLA_ms
    }

    print("=== Generation summary ===")
    print(f"Interfaces               : {len(interfaces)}")
    print(f"Events                   : {len(events)}")
    print(f"  Failed                 : {failed}")
    print(f"  Warning                : {warning}")
    print(f"Unique system-to-system dependencies : {len(deps)}")
    print(f"Interfaces with SLA violations       : {len(sla_violating_ifaces)}")
    print("All referential-integrity checks passed.")
    print("Wrote interface_master.csv and events.csv")


if __name__ == "__main__":
    main()
