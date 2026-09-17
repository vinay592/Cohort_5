"""
validation.py
-------------
Referential-integrity and semantic validation of the loaded DataBundle.
Returns a ValidationReport so the UI can display issues without crashing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pandas as pd

from src.data_loader import DataBundle

# Known system codes per spec
KNOWN_SYSTEMS = {"ORD", "MFG", "PRC", "ASM", "DLV", "PAY"}

# Statuses that are supported by default
KNOWN_STATUSES = {"Failed", "Warning", "Success", "Retry"}


@dataclass
class ValidationReport:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def validate(bundle: DataBundle) -> ValidationReport:
    report = ValidationReport()

    events = bundle.events
    im = bundle.interface_master
    pw = bundle.priority_weight
    piw = bundle.process_impact_weight
    cal = bundle.business_calendar

    # -----------------------------------------------------------------------
    # 1. Referential integrity: events.InterfaceID ⊆ interface_master.InterfaceID
    # -----------------------------------------------------------------------
    known_ifaces = set(im["InterfaceID"].dropna())
    bad_ifaces = set(events["InterfaceID"].dropna()) - known_ifaces
    if bad_ifaces:
        report.add_error(
            f"events.csv references unknown InterfaceIDs: {sorted(bad_ifaces)}"
        )

    # -----------------------------------------------------------------------
    # 2. Priority integrity: interface_master.Priority ⊆ priority_weight.Priority
    # -----------------------------------------------------------------------
    known_priorities = set(pw["Priority"].dropna())
    bad_priorities = set(im["Priority"].dropna()) - known_priorities
    if bad_priorities:
        report.add_error(
            f"interface_master.csv references unknown Priorities: {sorted(bad_priorities)}"
        )

    # -----------------------------------------------------------------------
    # 3. Process integrity: interface_master.BusinessProcess ⊆ process_impact_weight.BusinessProcess
    # -----------------------------------------------------------------------
    known_processes = set(piw["BusinessProcess"].dropna())
    bad_processes = set(im["BusinessProcess"].dropna()) - known_processes
    if bad_processes:
        report.add_error(
            f"interface_master.csv references unknown BusinessProcesses: {sorted(bad_processes)}"
        )

    # -----------------------------------------------------------------------
    # 4. PriorityWeight cross-check (interface_master vs. priority_weight)
    # -----------------------------------------------------------------------
    im_with_pw = im.merge(pw, on="Priority", suffixes=("_im", "_pw"), how="left")
    mismatch = im_with_pw[
        im_with_pw["PriorityWeight"] != im_with_pw["Weight"]
    ]
    if not mismatch.empty:
        report.add_warning(
            f"{len(mismatch)} interface(s) have PriorityWeight that disagrees with priority_weight.csv: "
            f"{mismatch['InterfaceID'].tolist()}"
        )

    # -----------------------------------------------------------------------
    # 5. Calendar integrity: every event timestamp maps to a calendar window
    # -----------------------------------------------------------------------
    bad_ts = events["Timestamp"].isna().sum()
    if bad_ts:
        report.add_error(f"{bad_ts} event(s) have unparseable Timestamps.")

    # -----------------------------------------------------------------------
    # 6. System integrity: SourceSystem / TargetSystem use known codes
    # -----------------------------------------------------------------------
    all_sources = set(im["SourceSystem"].dropna())
    all_targets = set(im["TargetSystem"].dropna())
    unknown_sys = (all_sources | all_targets) - KNOWN_SYSTEMS
    if unknown_sys:
        report.add_warning(
            f"Unknown system codes in interface_master: {sorted(unknown_sys)}"
        )

    # -----------------------------------------------------------------------
    # 7. Status integrity: events.Status ⊆ KNOWN_STATUSES
    # -----------------------------------------------------------------------
    unknown_statuses = set(events["Status"].dropna()) - KNOWN_STATUSES
    if unknown_statuses:
        report.add_warning(
            f"events.csv contains unknown Status values: {sorted(unknown_statuses)}"
        )

    # -----------------------------------------------------------------------
    # 8. Null checks on critical columns
    # -----------------------------------------------------------------------
    for col in ["EventID", "InterfaceID", "Status", "ErrorCode", "Timestamp"]:
        n = events[col].isna().sum()
        if n:
            report.add_warning(f"events.csv: {n} null value(s) in column '{col}'")

    return report
