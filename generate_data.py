"""
generate_data.py

Generates synthetic enterprise integration telemetry for a 6-system
environment (ORD, MFG, PRC, ASM, DLV, PAY):

  - interface_master.csv        (~15 interfaces, business-semantic priority)
  - events.csv                  (3,000 problem events: Failed / Warning)
  - priority_weight.csv         (5-row priority -> weight lookup)
  - process_impact_weight.csv   (BusinessProcess -> ProcessWeight, 0-100)
  - business_calendar.csv       (calendar windows covering the event range)

Design notes
------------
- events.InterfaceID is always a foreign key into interface_master.
- SourceSystem / TargetSystem / Middleware / Pattern on each event are
  always derived (copied) from the referenced interface, never
  independently randomized.
- Priority on each interface is assigned deterministically from the
  BusinessProcess text (business semantics), not from system name and
  not randomly. PriorityWeight is looked up from priority_weight.csv.
- ProcessWeight (business impact, 0-100) is likewise derived
  deterministically from BusinessProcess semantics, independent of
  Priority, and covers every unique BusinessProcess exactly once.
- business_calendar.csv defines a small set of contiguous windows
  (e.g. MEC / QEC / Normal) that together span the same 7-day range
  used for event timestamps, so every event maps to exactly one
  window with a CostMultiplier for impact-weighted analytics.
- Timestamps are spread over ~7 days with business-hour weighting and
  a handful of failure "bursts".
- A lightweight propagation pass links some upstream failures to
  downstream events (shared SessionID, close-in-time timestamps),
  simulating cascading failures across the dependency graph.
- The script self-validates the generated data before writing files
  and raises AssertionError on any violation.

Only the Python standard library is used. Deterministic when SEED is
fixed (default below).
"""

import csv
import random
import uuid
from datetime import datetime, timedelta, date
from collections import defaultdict, Counter

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

SEED = 42
N_EVENTS = 3000
START_DATE = datetime(2026, 9, 10, 0, 0, 0)   # 7-day window start
WINDOW_DAYS = 7

random.seed(SEED)

SYSTEMS = ["ORD", "MFG", "PRC", "ASM", "DLV", "PAY"]

# --------------------------------------------------------------------------
# 1. Priority model (priority_weight.csv)
# --------------------------------------------------------------------------

PRIORITY_WEIGHTS = [
    ("Critical", 100),
    ("High", 60),
    ("Elevated", 25),
    ("Normal", 5),
    ("Low", 2),
]
PRIORITY_WEIGHT_MAP = dict(PRIORITY_WEIGHTS)

# Criticality (P1/P2/P3) and base SLA band, derived from Priority.
PRIORITY_TO_CRITICALITY = {
    "Critical": "P1",
    "High": "P2",
    "Elevated": "P2",
    "Normal": "P3",
    "Low": "P3",
}
PRIORITY_TO_SLA_RANGE_MS = {
    "Critical": (150, 400),
    "High": (400, 800),
    "Elevated": (800, 1500),
    "Normal": (1500, 3000),
    "Low": (3000, 6000),
}


def classify_priority(business_process):
    """
    Deterministically derive Priority from the BUSINESS FUNCTION the
    interface performs (not from system name, not randomly).
    """
    b = business_process.lower()

    # Direct financial transactions: authorize / capture / charge / request money
    if "payment" in b:
        if any(k in b for k in ("authoriz", "capture", "charge", "request")):
            return "Critical"
        return "Elevated"  # e.g. payment status sync (informational)

    # Order lifecycle: creation/validation gate downstream production & payment
    if "order creation" in b or "order validation" in b:
        return "High"

    # Starting production stops the line if it fails
    if "production start" in b:
        return "Critical"

    # Assembly completion / start gate downstream delivery
    if "assembly completion" in b:
        return "High"
    if "assembly start" in b:
        return "High"

    # Fulfillment-facing operations
    if "shipment dispatch" in b or "delivery confirmation" in b:
        return "High"

    # Quality check: blocks downstream but not itself a financial/production stop
    if "quality check" in b:
        return "Elevated"

    # Procurement
    if "purchase order creation" in b:
        return "High"
    if "material receipt" in b:
        return "Elevated"

    # Inventory/stock: important but not automatically critical
    if "stock" in b or "inventory" in b:
        return "Elevated"

    # Informational / reference-data / supplier validation
    if "supplier validation" in b or "notification" in b or "reference" in b or "informational" in b:
        return "Normal"

    return "Normal"


def classify_process_weight(business_process):
    """
    Deterministically derive a 0-100 ProcessWeight (business impact if the
    process is disrupted) from the BusinessProcess text. Independent of,
    but semantically consistent with, classify_priority above.
    """
    b = business_process.lower()

    if "payment" in b:
        if any(k in b for k in ("authoriz", "capture")):
            return 100          # direct financial transaction
        if "request" in b:
            return 90           # initiates a financial transaction
        return 30                # status sync / informational

    if "production start" in b:
        return 90                # can stop the production line

    # Check the more specific "purchase order creation" before the generic
    # "order creation" pattern, since the former contains the latter as a
    # substring ("purchase " + "order creation").
    if "purchase order creation" in b:
        return 70                # upstream procurement trigger

    if "order creation" in b:
        return 95                # initiates the customer order lifecycle
    if "order validation" in b:
        return 80                # gates the order lifecycle

    if "assembly completion" in b:
        return 85                # blocks downstream fulfillment
    if "assembly start" in b:
        return 75

    if "shipment dispatch" in b or "delivery confirmation" in b:
        return 80                # directly affects fulfillment

    if "quality check" in b:
        return 65                # blocks downstream processing

    if "material receipt" in b:
        return 55

    if "stock" in b or "inventory" in b:
        return 35                # routine, generally non-blocking

    if "supplier validation" in b:
        return 15                # reference/informational

    if "notification" in b or "reference" in b or "informational" in b:
        return 20

    return 25  # conservative default for any unclassified process


# --------------------------------------------------------------------------
# 2. interface_master.csv definition
# --------------------------------------------------------------------------
# Each tuple: (id_suffix, Source, Target, Middleware, Pattern, BusinessProcess, Area)
# The dependency chain intentionally reuses edges (ORD->MFG, PRC->MFG, etc.)
# across multiple interfaces so the graph has repeated, meaningfully
# interconnected dependencies rather than 15 independent edges.

INTERFACE_DEFS = [
    ("IF_ORD_001", "ORD", "PAY", "API", "REST", "Payment Request", "Finance"),
    ("IF_PAY_001", "PAY", "ORD", "API", "REST", "Payment Authorization", "Finance"),
    ("IF_PAY_002", "PAY", "ORD", "ESB", "CDC", "Payment Status Sync", "Finance"),
    ("IF_ORD_002", "ORD", "MFG", "MsgBus", "Async", "Production Start Trigger", "Manufacturing"),
    ("IF_ORD_003", "ORD", "MFG", "API", "REST", "Order Validation", "Order Management"),
    ("IF_MFG_001", "MFG", "ASM", "MsgBus", "Async", "Assembly Start Trigger", "Assembly"),
    ("IF_MFG_002", "MFG", "ASM", "API", "REST", "Quality Check", "Assembly"),
    ("IF_MFG_003", "MFG", "ASM", "MsgBus", "CDC", "Inventory Stock Decrement", "Manufacturing"),
    ("IF_MFG_004", "MFG", "PRC", "MsgBus", "Async", "Material Requirement Notification", "Manufacturing"),
    ("IF_PRC_001", "PRC", "MFG", "ESB", "SOAP", "Purchase Order Creation", "Procurement"),
    ("IF_PRC_002", "PRC", "ASM", "Batch", "Batch", "Material Receipt", "Procurement"),
    ("IF_PRC_003", "PRC", "MFG", "API", "REST", "Supplier Validation", "Procurement"),
    ("IF_ASM_001", "ASM", "DLV", "MsgBus", "Async", "Assembly Completion", "Assembly"),
    ("IF_ASM_002", "ASM", "DLV", "API", "REST", "Shipment Dispatch", "Logistics"),
    ("IF_DLV_001", "DLV", "PAY", "API", "REST", "Delivery Confirmation Payment Capture", "Logistics"),
]

assert len(INTERFACE_DEFS) == 15, "Expected exactly 15 interface definitions"


def build_interface_master():
    interfaces = []
    for iid, src, tgt, mw, pattern, bp, area in INTERFACE_DEFS:
        assert src in SYSTEMS and tgt in SYSTEMS
        priority = classify_priority(bp)
        criticality = PRIORITY_TO_CRITICALITY[priority]
        sla_lo, sla_hi = PRIORITY_TO_SLA_RANGE_MS[priority]
        sla_ms = random.randint(sla_lo, sla_hi)
        interfaces.append({
            "InterfaceID": iid,
            "SourceSystem": src,
            "TargetSystem": tgt,
            "Middleware": mw,
            "Pattern": pattern,
            "BusinessProcess": bp,
            "Priority": priority,
            "Area": area,
            "Criticality": criticality,
            "SLA_ms": sla_ms,
            "PriorityWeight": PRIORITY_WEIGHT_MAP[priority],
        })
    return interfaces


def build_process_impact_weight(interfaces):
    """One row per unique BusinessProcess used in interface_master, with a
    deterministic, business-impact-derived ProcessWeight (0-100)."""
    unique_processes = sorted({i["BusinessProcess"] for i in interfaces})
    rows = []
    for bp in unique_processes:
        weight = classify_process_weight(bp)
        assert 0 <= weight <= 100
        rows.append({"BusinessProcess": bp, "ProcessWeight": weight})
    # Highest impact first, for a more readable file
    rows.sort(key=lambda r: -r["ProcessWeight"])
    return rows


# --------------------------------------------------------------------------
# 2b. business_calendar.csv definition
# --------------------------------------------------------------------------
# A small, contiguous set of windows that together span the same 7-day
# range used for event timestamps (START_DATE .. START_DATE + WINDOW_DAYS),
# so every event can be mapped to exactly one calendar window.

BUSINESS_CALENDAR = [
    # (WindowStart, WindowEnd, WindowType, CostMultiplier)
    (date(2026, 9, 10), date(2026, 9, 11), "MEC", 2.0),     # month-end-close ramp
    (date(2026, 9, 12), date(2026, 9, 13), "QEC", 3.0),     # quarter-end close
    (date(2026, 9, 14), date(2026, 9, 16), "Normal", 1.0),  # normal operations
]

# Sanity: calendar must cover the full event window with no gaps.
_calendar_start = BUSINESS_CALENDAR[0][0]
_calendar_end = BUSINESS_CALENDAR[-1][1]
assert _calendar_start == START_DATE.date(), "Calendar must start with the event window"
assert _calendar_end == (START_DATE + timedelta(days=WINDOW_DAYS - 1)).date(), (
    "Calendar must cover the full event window"
)


def find_calendar_window(ts):
    """Return the BUSINESS_CALENDAR row whose [WindowStart, WindowEnd] (inclusive,
    by date) contains the given event timestamp, or None if none matches."""
    d = ts.date()
    for w_start, w_end, w_type, mult in BUSINESS_CALENDAR:
        if w_start <= d <= w_end:
            return (w_start, w_end, w_type, mult)
    return None


# --------------------------------------------------------------------------
# 3. Error / root-cause catalog (per source system)
# --------------------------------------------------------------------------

ERROR_CATALOG = {
    "ORD": [
        ("ORD_DB_001", "Database", "Order database connection timeout"),
        ("ORD_VAL_002", "Validation", "Order validation failed due to missing required field"),
        ("ORD_AUTH_003", "Authentication", "Order service authentication token expired"),
        ("ORD_NET_004", "Network", "Network timeout while contacting order service"),
    ],
    "MFG": [
        ("MFG_MACHINE_001", "Infrastructure", "Manufacturing machine controller not responding"),
        ("MFG_QC_003", "Validation", "Quality check parameters out of tolerance"),
        ("MFG_CAP_004", "Capacity", "Manufacturing queue capacity exceeded"),
        ("MFG_DB_002", "Database", "Manufacturing execution database write failure"),
    ],
    "PRC": [
        ("PRC_PO_001", "ExternalService", "Purchase order rejected by supplier system"),
        ("PRC_MAT_002", "Timeout", "Material availability check timed out"),
        ("PRC_CFG_003", "Configuration", "Procurement routing configuration invalid"),
        ("PRC_AUTHZ_004", "Authorization", "Procurement user lacks approval authorization"),
    ],
    "ASM": [
        ("ASM_COMP_001", "Validation", "Assembly component mismatch detected"),
        ("ASM_DB_002", "Database", "Assembly tracking database update failed"),
        ("ASM_CAP_003", "Capacity", "Assembly line at maximum capacity"),
        ("ASM_NET_004", "Network", "Assembly station network connectivity lost"),
    ],
    "DLV": [
        ("DLV_ROUTE_001", "ExternalService", "Delivery routing service unavailable"),
        ("DLV_CFG_002", "Configuration", "Delivery zone configuration mismatch"),
        ("DLV_TIME_003", "Timeout", "Carrier API response timeout"),
        ("DLV_DB_004", "Database", "Delivery tracking database error"),
    ],
    "PAY": [
        ("PAY_AUTH_001", "Authentication", "Payment gateway authentication failed"),
        ("PAY_AUTHZ_002", "Authorization", "Payment authorization declined by issuer"),
        ("PAY_EXT_003", "ExternalService", "Payment processor external service error"),
        ("PAY_TIME_004", "Timeout", "Payment gateway response timeout"),
    ],
}

# Root causes that plausibly come with elevated latency
ELEVATED_LATENCY_ROOT_CAUSES = {"Timeout", "Network", "Database", "ExternalService"}

FAILED_BIAS_ROOT_CAUSES = {"Database", "Network", "Infrastructure", "Timeout", "ExternalService", "Capacity"}
WARNING_BIAS_ROOT_CAUSES = {"Validation", "Configuration", "Authentication", "Authorization"}


def pick_error(source_system, status):
    """Pick an error catalog entry for a system, biased by event status."""
    entries = ERROR_CATALOG[source_system]
    bias = FAILED_BIAS_ROOT_CAUSES if status == "Failed" else WARNING_BIAS_ROOT_CAUSES
    biased = [e for e in entries if e[1] in bias]
    pool = biased if biased and random.random() < 0.75 else entries
    return random.choice(pool)


# --------------------------------------------------------------------------
# 4. Timestamp generation (business-hour weighted, over WINDOW_DAYS)
# --------------------------------------------------------------------------

# Hourly weights: low overnight, ramps up during business hours, tapers evening
HOUR_WEIGHTS = [
    1, 1, 1, 1, 1, 2,     # 0-5
    3, 5, 8, 10, 10, 9,   # 6-11
    8, 9, 10, 10, 9, 8,   # 12-17
    6, 4, 3, 2, 2, 1,     # 18-23
]


def random_timestamp():
    day_offset = random.randint(0, WINDOW_DAYS - 1)
    hour = random.choices(range(24), weights=HOUR_WEIGHTS, k=1)[0]
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return START_DATE + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)


def burst_timestamp(center):
    """A timestamp clustered tightly around a center time (failure burst)."""
    delta = timedelta(minutes=random.randint(-20, 20), seconds=random.randint(0, 59))
    ts = center + delta
    # Clamp into the valid window
    lo = START_DATE
    hi = START_DATE + timedelta(days=WINDOW_DAYS) - timedelta(seconds=1)
    if ts < lo:
        ts = lo
    if ts > hi:
        ts = hi
    return ts


# --------------------------------------------------------------------------
# 5. Event allocation per interface (weighted by business PriorityWeight
#    so critical-path interfaces get proportionally more traffic, while
#    every interface still gets a healthy minimum count)
# --------------------------------------------------------------------------

def allocate_event_counts(interfaces, total):
    min_per_interface = 60
    weights = [iface["PriorityWeight"] for iface in interfaces]
    weight_sum = sum(weights)
    remaining = total - min_per_interface * len(interfaces)
    assert remaining > 0, "N_EVENTS too small for min_per_interface allocation"

    raw = [remaining * w / weight_sum for w in weights]
    counts = [min_per_interface + int(r) for r in raw]

    # Largest-remainder method to hit the exact total
    diff = total - sum(counts)
    remainders = sorted(
        range(len(interfaces)),
        key=lambda i: (remaining * weights[i] / weight_sum) - int(remaining * weights[i] / weight_sum),
        reverse=True,
    )
    idx = 0
    while diff != 0:
        i = remainders[idx % len(remainders)]
        if diff > 0:
            counts[i] += 1
            diff -= 1
        else:
            if counts[i] > min_per_interface:
                counts[i] -= 1
                diff += 1
        idx += 1

    assert sum(counts) == total
    return {iface["InterfaceID"]: c for iface, c in zip(interfaces, counts)}


# --------------------------------------------------------------------------
# 6. Build events.csv
# --------------------------------------------------------------------------

# Curated upstream -> downstream propagation chains (by InterfaceID), used
# to correlate some failures with plausible downstream effects.
PROPAGATION_CHAINS = [
    ("IF_ORD_002", "IF_MFG_001"),   # Production start failure -> assembly start warning
    ("IF_ORD_002", "IF_MFG_002"),   # Production start failure -> quality check warning
    ("IF_MFG_001", "IF_ASM_001"),   # Assembly start failure -> assembly completion warning
    ("IF_PRC_001", "IF_MFG_001"),   # PO creation failure -> assembly start warning
    ("IF_PAY_001", "IF_ORD_002"),   # Payment auth failure -> production start warning
    ("IF_PAY_001", "IF_ORD_003"),   # Payment auth failure -> order validation warning
    ("IF_ASM_001", "IF_ASM_002"),   # Assembly completion failure -> shipment dispatch warning
    ("IF_ASM_002", "IF_DLV_001"),   # Shipment dispatch failure -> delivery/payment capture warning
]


def build_events(interfaces):
    iface_by_id = {i["InterfaceID"]: i for i in interfaces}
    counts = allocate_event_counts(interfaces, N_EVENTS)

    # Session pool: several events share a SessionID to allow correlation.
    n_sessions = max(1, N_EVENTS // 5)
    session_pool = [f"SESS_{uuid.UUID(int=random.getrandbits(128)).hex[:12]}" for _ in range(n_sessions)]

    events = []
    event_seq = 1

    for iface_id, count in counts.items():
        iface = iface_by_id[iface_id]
        for _ in range(count):
            status = "Failed" if random.random() < 0.60 else "Warning"
            code, root_cause, text = pick_error(iface["SourceSystem"], status)

            # Base latency, elevated for certain root-cause categories
            if root_cause in ELEVATED_LATENCY_ROOT_CAUSES:
                latency = random.randint(2000, 9000)
            else:
                latency = random.randint(80, 2000)

            # Occasionally force an SLA violation regardless of root cause
            if random.random() < 0.18:
                latency = max(latency, int(iface["SLA_ms"] * random.uniform(1.2, 3.0)))

            ts = random_timestamp()
            # Occasional overnight/failure burst clustering: nudge ~15% of
            # events for high/critical interfaces into a tight cluster.
            if iface["Priority"] in ("Critical", "High") and random.random() < 0.15:
                ts = burst_timestamp(ts)

            events.append({
                "EventID": f"EVT_{event_seq:06d}",
                "InterfaceID": iface["InterfaceID"],
                "SourceSystem": iface["SourceSystem"],
                "TargetSystem": iface["TargetSystem"],
                "Middleware": iface["Middleware"],
                "Pattern": iface["Pattern"],
                "Status": status,
                "ErrorCode": code,
                "ErrorText": text,
                "RootCauseClass": root_cause,
                "Latency_ms": latency,
                "SessionID": random.choice(session_pool),
                "RequestID": f"REQ_{uuid.uuid4().hex[:16]}",
                "Timestamp": ts,
            })
            event_seq += 1

    assert len(events) == N_EVENTS

    # ---- Failure propagation pass -----------------------------------
    # For a sample of chains, pick a Failed event on the upstream
    # interface and correlate a random downstream event with it:
    # shared SessionID, timestamp shortly after, and a note appended
    # to the downstream error text.
    events_by_iface = defaultdict(list)
    for e in events:
        events_by_iface[e["InterfaceID"]].append(e)

    n_propagations = 150
    for _ in range(n_propagations):
        up_id, down_id = random.choice(PROPAGATION_CHAINS)
        up_candidates = [e for e in events_by_iface[up_id] if e["Status"] == "Failed"]
        down_candidates = events_by_iface.get(down_id)
        if not up_candidates or not down_candidates:
            continue
        upstream = random.choice(up_candidates)
        downstream = random.choice(down_candidates)

        downstream["SessionID"] = upstream["SessionID"]
        delay = timedelta(minutes=random.randint(1, 15), seconds=random.randint(0, 59))
        new_ts = upstream["Timestamp"] + delay
        lo = START_DATE
        hi = START_DATE + timedelta(days=WINDOW_DAYS) - timedelta(seconds=1)
        downstream["Timestamp"] = min(max(new_ts, lo), hi)
        if "(correlated with upstream failure on" not in downstream["ErrorText"]:
            downstream["ErrorText"] = (
                f"{downstream['ErrorText']} (correlated with upstream failure on {up_id})"
            )

    return events


# --------------------------------------------------------------------------
# 7. Validation
# --------------------------------------------------------------------------

def validate(interfaces, events, priority_weight_rows, process_impact_rows, calendar_rows):
    iface_ids = {i["InterfaceID"] for i in interfaces}
    iface_by_id = {i["InterfaceID"]: i for i in interfaces}

    # --- Core structural checks ---
    assert len(interfaces) == 15, f"Expected 15 interfaces, got {len(interfaces)}"
    assert len(events) == N_EVENTS, f"Expected {N_EVENTS} events, got {len(events)}"

    event_ids = [e["EventID"] for e in events]
    assert len(event_ids) == len(set(event_ids)), "Duplicate EventID found"

    request_ids = [e["RequestID"] for e in events]
    assert len(request_ids) == len(set(request_ids)), "Duplicate RequestID found"

    window_start = START_DATE
    window_end = START_DATE + timedelta(days=WINDOW_DAYS)

    dependency_edges = Counter()
    interface_event_counts = Counter()
    window_type_counts = Counter()

    for e in events:
        assert e["InterfaceID"], "Null InterfaceID found"
        assert e["InterfaceID"] in iface_ids, f"Unknown InterfaceID {e['InterfaceID']} in events"
        iface = iface_by_id[e["InterfaceID"]]

        assert e["SourceSystem"] == iface["SourceSystem"], "SourceSystem mismatch"
        assert e["TargetSystem"] == iface["TargetSystem"], "TargetSystem mismatch"
        assert e["Middleware"] == iface["Middleware"], "Middleware mismatch"
        assert e["Pattern"] == iface["Pattern"], "Pattern mismatch"

        assert e["Status"] in ("Failed", "Warning"), f"Invalid Status {e['Status']}"
        assert e["ErrorCode"], "Null ErrorCode found"
        assert window_start <= e["Timestamp"] < window_end, "Timestamp outside 7-day window"
        assert isinstance(e["Latency_ms"], int) and e["Latency_ms"] > 0, "Latency_ms must be a positive int"

        dependency_edges[(iface["SourceSystem"], iface["TargetSystem"])] += 1
        interface_event_counts[e["InterfaceID"]] += 1

        window = find_calendar_window(e["Timestamp"])
        assert window is not None, f"Event {e['EventID']} does not map to any business-calendar window"
        window_type_counts[window[2]] += 1

    # Every interface must have multiple observations
    for iid in iface_ids:
        assert interface_event_counts[iid] >= 2, f"Interface {iid} has fewer than 2 events"

    # Graph must have multiple connected paths (edges) with real traffic
    assert len(dependency_edges) >= 5, "Dependency graph has too few distinct edges"
    # Confirm key required edges exist
    required_edges = {("ORD", "MFG"), ("ORD", "PAY"), ("PRC", "MFG"),
                       ("PRC", "ASM"), ("MFG", "ASM"), ("ASM", "DLV"), ("PAY", "ORD")}
    present_edges = set(dependency_edges.keys())
    missing = required_edges - present_edges
    assert not missing, f"Missing required dependency edges: {missing}"

    # --- Priority model checks ---
    assert len(priority_weight_rows) == 5, "priority_weight.csv must have exactly 5 rows"
    expected_priorities = ["Critical", "High", "Elevated", "Normal", "Low"]
    expected_weights = [100, 60, 25, 5, 2]
    got_priorities = [r["Priority"] for r in priority_weight_rows]
    got_weights = [r["Weight"] for r in priority_weight_rows]
    assert got_priorities == expected_priorities, f"Priority levels mismatch: {got_priorities}"
    assert got_weights == expected_weights, f"Priority weights mismatch: {got_weights}"

    pw_map = dict(zip(got_priorities, got_weights))
    for iface in interfaces:
        assert iface["Priority"] in pw_map, f"Invalid Priority on {iface['InterfaceID']}"
        assert iface["PriorityWeight"] == pw_map[iface["Priority"]], (
            f"PriorityWeight mismatch on {iface['InterfaceID']}"
        )

    # Business-semantic sanity checks (not merely system-name based)
    for iface in interfaces:
        bp = iface["BusinessProcess"].lower()
        if "payment" in bp and any(k in bp for k in ("authoriz", "capture", "charge", "request")):
            assert iface["Priority"] == "Critical", (
                f"Financial transaction interface {iface['InterfaceID']} should be Critical"
            )
        if "stock" in bp or "inventory" in bp:
            assert iface["Priority"] != "Critical", (
                f"Routine stock/inventory interface {iface['InterfaceID']} should not be Critical"
            )
        if "supplier validation" in bp or "notification" in bp:
            assert iface["Priority"] not in ("Critical",), (
                f"Informational interface {iface['InterfaceID']} should not be Critical"
            )

    # --- process_impact_weight checks ---
    used_processes = {i["BusinessProcess"] for i in interfaces}
    pw_rows_by_process = Counter(r["BusinessProcess"] for r in process_impact_rows)
    for bp, n in pw_rows_by_process.items():
        assert n == 1, f"BusinessProcess '{bp}' appears {n} times in process_impact_weight.csv (must be exactly 1)"
    mapped_processes = set(pw_rows_by_process.keys())
    assert used_processes == mapped_processes, (
        f"process_impact_weight.csv does not exactly cover interface_master BusinessProcess values. "
        f"Missing: {used_processes - mapped_processes}, Extra/unused: {mapped_processes - used_processes}"
    )
    for r in process_impact_rows:
        assert isinstance(r["ProcessWeight"], int), "ProcessWeight must be an integer"
        assert 0 <= r["ProcessWeight"] <= 100, f"ProcessWeight out of range for {r['BusinessProcess']}"
        # Re-derive to confirm it is a deterministic function of business semantics, not random
        assert r["ProcessWeight"] == classify_process_weight(r["BusinessProcess"]), (
            f"ProcessWeight for {r['BusinessProcess']} is not reproducible from its business semantics"
        )
    for r in process_impact_rows:
        b = r["BusinessProcess"].lower()
        if "payment" in b and any(k in b for k in ("authoriz", "capture")):
            assert r["ProcessWeight"] >= 90, f"Financial process {r['BusinessProcess']} should have high impact weight"
        if ("stock" in b or "inventory" in b) and "production" not in b:
            assert r["ProcessWeight"] < 100, f"Routine stock/inventory process {r['BusinessProcess']} should not be max impact"

    # --- business_calendar checks ---
    assert len(calendar_rows) > 0, "business_calendar.csv must not be empty"
    for w_start, w_end, w_type, mult in calendar_rows:
        assert w_start <= w_end, f"WindowStart after WindowEnd for {w_type}"
        assert mult > 0, f"CostMultiplier must be positive for {w_type}"
    # Every event was already confirmed above to map to a window (assert inside the loop).
    assert sum(window_type_counts.values()) == len(events), "Not all events mapped to a calendar window"

    return {
        "dependency_edges": dependency_edges,
        "interface_event_counts": interface_event_counts,
        "window_type_counts": window_type_counts,
    }


# --------------------------------------------------------------------------
# 8. Write CSVs
# --------------------------------------------------------------------------

def write_interface_master(interfaces, path="interface_master.csv"):
    fields = ["InterfaceID", "SourceSystem", "TargetSystem", "Middleware", "Pattern",
              "BusinessProcess", "Priority", "Area", "Criticality", "SLA_ms", "PriorityWeight"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in interfaces:
            w.writerow(row)


def write_events(events, path="events.csv"):
    fields = ["EventID", "InterfaceID", "SourceSystem", "TargetSystem", "Middleware", "Pattern",
              "Status", "ErrorCode", "ErrorText", "RootCauseClass", "Latency_ms",
              "SessionID", "RequestID", "Timestamp"]
    events_sorted = sorted(events, key=lambda e: e["Timestamp"])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for e in events_sorted:
            row = dict(e)
            row["Timestamp"] = e["Timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            w.writerow(row)


def write_priority_weight(path="priority_weight.csv"):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Priority", "Weight"])
        for p, weight in PRIORITY_WEIGHTS:
            w.writerow([p, weight])
    return [{"Priority": p, "Weight": weight} for p, weight in PRIORITY_WEIGHTS]


def write_process_impact_weight(rows, path="process_impact_weight.csv"):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["BusinessProcess", "ProcessWeight"])
        w.writeheader()
        for row in rows:
            w.writerow(row)


def write_business_calendar(path="business_calendar.csv"):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["WindowStart", "WindowEnd", "WindowType", "CostMultiplier"])
        for w_start, w_end, w_type, mult in BUSINESS_CALENDAR:
            w.writerow([w_start.isoformat(), w_end.isoformat(), w_type, mult])
    return list(BUSINESS_CALENDAR)


# --------------------------------------------------------------------------
# 9. Main
# --------------------------------------------------------------------------

def main():
    interfaces = build_interface_master()
    events = build_events(interfaces)
    priority_weight_rows = write_priority_weight()
    process_impact_rows = build_process_impact_weight(interfaces)
    calendar_rows = list(BUSINESS_CALENDAR)

    stats = validate(interfaces, events, priority_weight_rows, process_impact_rows, calendar_rows)

    write_interface_master(interfaces)
    write_events(events)
    write_process_impact_weight(process_impact_rows)
    write_business_calendar()

    # ---- Summary ----
    failed = sum(1 for e in events if e["Status"] == "Failed")
    warning = sum(1 for e in events if e["Status"] == "Warning")
    sla_flags = {
        e["EventID"]: e["Latency_ms"] > next(i["SLA_ms"] for i in interfaces if i["InterfaceID"] == e["InterfaceID"])
        for e in events
    }
    sla_violation_events = sum(sla_flags.values())
    sla_violation_interfaces = len({
        e["InterfaceID"] for e in events
        if e["Latency_ms"] > next(i["SLA_ms"] for i in interfaces if i["InterfaceID"] == e["InterfaceID"])
    })
    priority_counts = Counter(i["Priority"] for i in interfaces)

    print("=" * 60)
    print("Synthetic Data Generation Summary")
    print("=" * 60)
    print(f"Interfaces generated:        {len(interfaces)}")
    print(f"Events generated:            {len(events)}")
    print(f"  Failed:                    {failed} ({failed/len(events):.1%})")
    print(f"  Warning:                   {warning} ({warning/len(events):.1%})")
    print(f"Unique system->system edges: {len(stats['dependency_edges'])}")
    for (src, tgt), n in sorted(stats["dependency_edges"].items(), key=lambda x: -x[1]):
        print(f"    {src} -> {tgt}: {n} events")
    print(f"Interfaces with SLA violations present: {sla_violation_interfaces}")
    print(f"Total events exceeding their interface SLA: {sla_violation_events}")

    print("Interface count by Priority:")
    for p, _ in PRIORITY_WEIGHTS:
        print(f"    {p}: {priority_counts.get(p, 0)}")
    print("Priority -> Weight mapping: OK "
          f"({', '.join(f'{p}={w}' for p, w in PRIORITY_WEIGHTS)})")

    print("BusinessProcess -> ProcessWeight mapping:")
    for r in process_impact_rows:
        print(f"    {r['BusinessProcess']}: {r['ProcessWeight']}")

    print("Event count by business-calendar WindowType:")
    for w_type, n in stats["window_type_counts"].most_common():
        print(f"    {w_type}: {n}")
    print("Available WindowType -> CostMultiplier combinations:")
    for w_start, w_end, w_type, mult in calendar_rows:
        print(f"    {w_type}: {mult}x  ({w_start} to {w_end})")

    print("-" * 60)
    print("All referential-integrity checks passed.")
    print("All priority-weight mappings passed.")
    print("All process-impact-weight mappings passed.")
    print("All business-calendar validations passed.")
    print("All dependency/graph consistency checks passed.")
    print("=" * 60)
    print("Files written: interface_master.csv, events.csv, priority_weight.csv, "
          "process_impact_weight.csv, business_calendar.csv")


if __name__ == "__main__":
    main()
