"""Render a :class:`Report` as JSON, terminal text, or a standalone HTML
compliance matrix suitable for emailing to an architect or contractor.
"""

from __future__ import annotations

import html
import json

from .models import FindingStatus, Report

_STATUS_LABEL = {
    FindingStatus.MET: "MET",
    FindingStatus.MISSING: "MISSING",
    FindingStatus.STANDARD_MISMATCH: "STANDARD MISMATCH",
    FindingStatus.VALUE_DEVIATION: "VALUE DEVIATION",
    FindingStatus.UNVERIFIED: "REVIEW",
}

_STATUS_COLOR = {
    FindingStatus.MET: "#1a7f37",
    FindingStatus.MISSING: "#cf222e",
    FindingStatus.STANDARD_MISMATCH: "#cf222e",
    FindingStatus.VALUE_DEVIATION: "#bc4c00",
    FindingStatus.UNVERIFIED: "#9a6700",
}


def to_dict(report: Report) -> dict:
    return {
        "section": report.section,
        "compliant": report.compliant,
        "summary": report.summary(),
        "findings": [
            {
                "status": f.status.value,
                "requirement": f.requirement.label(),
                "kind": f.requirement.kind.value,
                "detail": f.detail,
                "evidence": f.evidence,
            }
            for f in report.findings
        ],
    }


def to_json(report: Report, indent: int = 2) -> str:
    return json.dumps(to_dict(report), indent=indent)


def to_text(report: Report) -> str:
    lines = [
        f"Section {report.section or '(unknown)'} — "
        f"{'APPROVE' if report.compliant else 'REVISE & RESUBMIT'}",
        "summary: " + ", ".join(f"{k}={v}" for k, v in report.summary().items()),
        "-" * 64,
    ]
    for f in report.findings:
        lines.append(f"[{_STATUS_LABEL[f.status]:<18}] {f.requirement.label()}")
        if f.detail:
            lines.append(f"    {f.detail}")
    return "\n".join(lines)


def to_html(report: Report) -> str:
    rows = []
    for f in report.findings:
        color = _STATUS_COLOR[f.status]
        rows.append(
            "<tr>"
            f'<td><span class="badge" style="background:{color}">'
            f"{_STATUS_LABEL[f.status]}</span></td>"
            f"<td>{html.escape(f.requirement.label())}</td>"
            f"<td>{html.escape(f.requirement.kind.value)}</td>"
            f"<td>{html.escape(f.detail)}</td>"
            "</tr>"
        )
    verdict = "APPROVE" if report.compliant else "REVISE &amp; RESUBMIT"
    verdict_color = "#1a7f37" if report.compliant else "#cf222e"
    summary = ", ".join(f"{k}: {v}" for k, v in report.summary().items())
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Submittal Review — {html.escape(report.section)}</title>
<style>
 body{{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:2rem;color:#1f2328}}
 h1{{font-size:1.3rem;margin:0 0 .25rem}}
 .verdict{{font-weight:700;color:{verdict_color}}}
 .meta{{color:#656d76;margin-bottom:1rem}}
 table{{border-collapse:collapse;width:100%}}
 th,td{{text-align:left;padding:.5rem .6rem;border-bottom:1px solid #d0d7de;vertical-align:top}}
 th{{background:#f6f8fa;font-size:.8rem;text-transform:uppercase;letter-spacing:.03em}}
 .badge{{color:#fff;padding:.1rem .5rem;border-radius:.7rem;font-size:.72rem;white-space:nowrap}}
</style></head><body>
<h1>Submittal Compliance Review — Section {html.escape(report.section or "N/A")}</h1>
<div class="meta">Verdict: <span class="verdict">{verdict}</span> &nbsp;·&nbsp; {html.escape(summary)}</div>
<table><thead><tr><th>Status</th><th>Requirement</th><th>Type</th><th>Detail</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
</body></html>"""
