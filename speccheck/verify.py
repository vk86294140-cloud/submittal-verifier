"""Cross-reference engine.

Given the requirements extracted from a spec section and the parsed contents
of a submittal, decide, requirement by requirement, whether the submittal
satisfies it. Output is a :class:`Report` of findings.
"""

from __future__ import annotations

import re

from .extract import NUM_RE, STANDARD_RE, _canon_unit, _normalize_num, content_words
from .models import (
    Finding,
    FindingStatus,
    Report,
    Requirement,
    RequirementKind,
    SubmittalDoc,
)

# Submittal item synonyms so "shop drawings" in the spec matches "shop dwgs"
# or a heading like "Drawings" in the submittal.
ITEM_SYNONYMS = {
    "shop drawing": ("shop drawing", "shop dwg", "drawings", "shop dwgs"),
    "product data": ("product data", "data sheet", "datasheet", "cut sheet", "technical data"),
    "sample": ("sample", "samples", "physical sample"),
    "test report": ("test report", "test data", "test results", "lab report"),
    "certificate": ("certificate", "certification", "certificate of compliance", "coc"),
    "warranty": ("warranty", "guarantee"),
    "maintenance data": ("maintenance data", "o&m", "operation and maintenance"),
    "calculation": ("calculation", "calc", "engineering calculation"),
}


def parse_submittal(text: str) -> SubmittalDoc:
    """Extract the cross-checkable facts from a submittal document."""
    doc = SubmittalDoc(raw_text=text)

    for m in STANDARD_RE.finditer(text):
        doc.standards.add(re.sub(r"\s+", " ", m.group()).strip().rstrip(".,;"))

    low = text.lower()
    for canon, words in ITEM_SYNONYMS.items():
        if any(w in low for w in words):
            doc.provided_items.append(canon)

    for m in NUM_RE.finditer(text):
        value = _normalize_num(m.group("num"))
        if value is None:
            continue
        keyword = text[max(0, m.start() - 40) : m.start()].strip().split()
        doc.numbers.append((value, _canon_unit(m.group("unit")), " ".join(keyword[-3:]).lower()))

    return doc


def verify(requirements: list[Requirement], submittal: SubmittalDoc) -> Report:
    section = requirements[0].section if requirements else ""
    report = Report(section=section)
    for req in requirements:
        report.findings.append(_check(req, submittal))
    report.findings.sort(key=lambda f: f.severity, reverse=True)
    return report


def _check(req: Requirement, sub: SubmittalDoc) -> Finding:
    if req.kind is RequirementKind.STANDARD:
        return _check_standard(req, sub)
    if req.kind is RequirementKind.SUBMITTAL_ITEM:
        return _check_item(req, sub)
    if req.kind is RequirementKind.NUMERIC:
        return _check_numeric(req, sub)
    return Finding(req, FindingStatus.UNVERIFIED, detail="Narrative requirement — manual review needed.")


def _check_standard(req: Requirement, sub: SubmittalDoc) -> Finding:
    want = _std_key(req.keyword)
    for cited in sub.standards:
        if _std_key(cited) == want:
            return Finding(req, FindingStatus.MET, detail=f"Submittal cites {cited}.", evidence=cited)
    # Same standard family (e.g. ASTM E84) but different number is a mismatch
    # worth flagging rather than a silent miss.
    family = want.split()[0] if want else ""
    near = [s for s in sub.standards if s.upper().startswith(family)]
    if near:
        return Finding(
            req,
            FindingStatus.STANDARD_MISMATCH,
            detail=f"Spec requires {req.keyword}; submittal cites {', '.join(near)}.",
            evidence=", ".join(near),
        )
    return Finding(req, FindingStatus.MISSING, detail=f"No reference to {req.keyword} found in submittal.")


def _check_item(req: Requirement, sub: SubmittalDoc) -> Finding:
    if req.keyword in sub.provided_items:
        return Finding(
            req, FindingStatus.MET, detail=f"'{req.keyword}' present in submittal.", evidence=req.keyword
        )
    return Finding(req, FindingStatus.MISSING, detail=f"Required submittal item '{req.keyword}' not found.")


def _check_numeric(req: Requirement, sub: SubmittalDoc) -> Finding:
    if req.quantity is None or not req.keyword:
        # No discriminating noun to bind the threshold to a submitted value;
        # report for manual review rather than guess.
        return Finding(
            req,
            FindingStatus.UNVERIFIED,
            detail="Numeric requirement without a clear subject — review manually.",
        )
    candidates = [
        (val, unit, kw)
        for (val, unit, kw) in sub.numbers
        if unit == req.unit and _keyword_overlap(req.keyword, kw)
    ]
    if not candidates:
        return Finding(
            req, FindingStatus.UNVERIFIED, detail=f"No comparable '{req.keyword}' value found in submittal."
        )

    val, unit, kw = candidates[0]
    ok = {
        "min": val >= req.quantity,
        "max": val <= req.quantity,
        "exact": abs(val - req.quantity) < 1e-6,
    }.get(req.bound, val == req.quantity)

    evidence = f"{val} {unit} ({kw})"
    if ok:
        return Finding(
            req, FindingStatus.MET, detail=f"Submitted {evidence} satisfies {req.label()}.", evidence=evidence
        )
    return Finding(
        req,
        FindingStatus.VALUE_DEVIATION,
        detail=f"Submitted {evidence} violates {req.label()}.",
        evidence=evidence,
    )


def _std_key(std: str) -> str:
    """Canonicalize a standard citation for comparison."""
    return re.sub(r"\s+", " ", std.upper().replace("-", " ")).strip()


def _keyword_overlap(a: str, b: str) -> bool:
    """True when spec and submittal numeric contexts share a real noun.

    Requires a discriminating word in common; an empty context never matches,
    so unrelated numbers are not bound together.
    """
    aw, bw = content_words(a), content_words(b)
    return bool(aw and bw and (aw & bw))
