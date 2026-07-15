"""Resubmittal tracking.

When a contractor resubmits after a "revise and resubmit", the reviewer's real
question is not "is this compliant?" but "did they fix what I flagged, and did
they break anything new?" This module diffs a fresh :class:`Report` against the
findings of a previously saved review and sorts the blocking items into three
buckets: cleared, recurring, and newly introduced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import FindingStatus, Report
from .report import to_dict

# Statuses that block approval and therefore must be tracked across rounds.
BLOCKING = {
    FindingStatus.MISSING.value,
    FindingStatus.STANDARD_MISMATCH.value,
    FindingStatus.VALUE_DEVIATION.value,
}


@dataclass
class ResubmittalDiff:
    section: str
    cleared: list[str] = field(default_factory=list)  # fixed since last round
    recurring: list[str] = field(default_factory=list)  # still unresolved
    new: list[str] = field(default_factory=list)  # regressions

    @property
    def resolved_all(self) -> bool:
        return not self.recurring and not self.new

    def as_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "cleared": self.cleared,
            "recurring": self.recurring,
            "new": self.new,
            "resolved_all": self.resolved_all,
        }


def _blocking_labels(findings: list[dict[str, Any]]) -> set[str]:
    return {str(f["requirement"]) for f in findings if f["status"] in BLOCKING}


def diff(prior_findings: list[dict[str, Any]], current: Report) -> ResubmittalDiff:
    """Compare a prior review's findings (as stored dicts) with a new report."""
    prior = _blocking_labels(prior_findings)
    current_findings = to_dict(current)["findings"]
    assert isinstance(current_findings, list)
    now = _blocking_labels(current_findings)
    return ResubmittalDiff(
        section=current.section,
        cleared=sorted(prior - now),
        recurring=sorted(prior & now),
        new=sorted(now - prior),
    )


def render(d: ResubmittalDiff) -> str:
    headline = "ALL PRIOR ISSUES RESOLVED" if d.resolved_all else "OUTSTANDING ISSUES REMAIN"
    lines = [f"Resubmittal diff — Section {d.section or '(unknown)'}: {headline}"]
    for title, items in (("Cleared", d.cleared), ("Recurring", d.recurring), ("New", d.new)):
        lines.append(f"  {title} ({len(items)}):")
        if items:
            lines.extend(f"    - {label}" for label in items)
        else:
            lines.append("    (none)")
    return "\n".join(lines)
