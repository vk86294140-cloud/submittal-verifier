"""Domain model for spec/submittal verification.

A *project specification* is organized into CSI MasterFormat sections (e.g.
``09 68 13 - Tile Carpeting``). Each section states (a) the items a contractor
must submit and (b) the material/performance requirements those products must
meet. A *submittal* is the contractor's response. Verification produces a set
of findings, one per requirement we were able to check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RequirementKind(str, Enum):
    """What sort of obligation a requirement expresses."""

    SUBMITTAL_ITEM = "submittal_item"   # "Submit product data for ..."
    STANDARD = "standard"               # "Comply with ASTM E84 ..."
    NUMERIC = "numeric"                 # "minimum 0.27 inch pile height"
    GENERAL = "general"                 # any other "shall/must" clause


class FindingStatus(str, Enum):
    MET = "met"
    MISSING = "missing"                 # required item absent from submittal
    STANDARD_MISMATCH = "standard_mismatch"
    VALUE_DEVIATION = "value_deviation"
    UNVERIFIED = "unverified"           # parsed, but not auto-checkable


# Severity ordering used for sorting/reporting. Higher = more urgent.
SEVERITY = {
    FindingStatus.MISSING: 3,
    FindingStatus.STANDARD_MISMATCH: 3,
    FindingStatus.VALUE_DEVIATION: 2,
    FindingStatus.UNVERIFIED: 1,
    FindingStatus.MET: 0,
}


@dataclass
class Requirement:
    """A single obligation extracted from the spec."""

    kind: RequirementKind
    text: str                       # verbatim clause from the spec
    section: str = ""               # e.g. "09 68 13"
    keyword: str = ""               # canonical token, e.g. "ASTM E84"
    # For NUMERIC requirements:
    quantity: Optional[float] = None
    unit: str = ""
    bound: str = ""                 # "min" | "max" | "exact"

    def label(self) -> str:
        if self.kind is RequirementKind.STANDARD:
            return f"Comply with {self.keyword}"
        if self.kind is RequirementKind.NUMERIC:
            b = {"min": ">=", "max": "<=", "exact": "="}.get(self.bound, "")
            return f"{self.keyword or 'value'} {b} {self.quantity} {self.unit}".strip()
        return self.text.strip()


@dataclass
class SubmittalDoc:
    """Parsed contents of a contractor submittal."""

    raw_text: str
    standards: set[str] = field(default_factory=set)         # cited standards
    provided_items: list[str] = field(default_factory=list)  # listed deliverables
    numbers: list[tuple[float, str, str]] = field(default_factory=list)
    # numbers: (value, unit, surrounding_keyword)


@dataclass
class Finding:
    requirement: Requirement
    status: FindingStatus
    detail: str = ""                # human-readable explanation
    evidence: str = ""              # snippet from submittal supporting the call

    @property
    def severity(self) -> int:
        return SEVERITY[self.status]


@dataclass
class Report:
    section: str
    findings: list[Finding] = field(default_factory=list)

    def by_status(self, status: FindingStatus) -> list[Finding]:
        return [f for f in self.findings if f.status is status]

    @property
    def compliant(self) -> bool:
        """True when nothing blocks approval (no missing items / mismatches)."""
        blocking = (FindingStatus.MISSING, FindingStatus.STANDARD_MISMATCH,
                    FindingStatus.VALUE_DEVIATION)
        return not any(f.status in blocking for f in self.findings)

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.status.value] = counts.get(f.status.value, 0) + 1
        return counts
