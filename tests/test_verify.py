from pathlib import Path

from speccheck import extract_requirements, parse_submittal, review, verify
from speccheck.models import FindingStatus, Requirement, RequirementKind, SubmittalDoc

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def test_met_standard():
    req = [Requirement(RequirementKind.STANDARD, "x", keyword="ASTM E648")]
    sub = SubmittalDoc(raw_text="complies with ASTM E648", standards={"ASTM E648"})
    rep = verify(req, sub)
    assert rep.findings[0].status is FindingStatus.MET


def test_missing_item():
    req = extract_requirements("Submit test reports from an independent agency.")
    sub = parse_submittal("Product data only enclosed.")
    statuses = {f.status for f in verify(req, sub).findings}
    assert FindingStatus.MISSING in statuses


def test_value_deviation():
    req = extract_requirements("Minimum pile height of 0.27 inch.")
    sub = parse_submittal("Pile height: 0.20 inch.")
    numeric = [f for f in verify(req, sub).findings if f.requirement.kind is RequirementKind.NUMERIC]
    assert numeric and numeric[0].status is FindingStatus.VALUE_DEVIATION


def test_value_met():
    req = extract_requirements("Minimum pile height of 0.27 inch.")
    sub = parse_submittal("Pile height: 0.30 inch.")
    numeric = [f for f in verify(req, sub).findings if f.requirement.kind is RequirementKind.NUMERIC]
    assert numeric and numeric[0].status is FindingStatus.MET


def test_standard_mismatch():
    req = extract_requirements("Comply with ASTM E662 for smoke density.")
    sub = parse_submittal("Tested to ASTM E84 for surface burning.")
    findings = verify(req, sub).findings
    assert any(f.status is FindingStatus.STANDARD_MISMATCH for f in findings)


def test_end_to_end_samples_revise():
    spec = (SAMPLES / "spec_096813.txt").read_text()
    submittal = (SAMPLES / "submittal_096813.txt").read_text()
    report = review(spec, submittal)
    # Sample submittal omits test reports + maintenance data and underspecs
    # pile height, so it must not be auto-approved.
    assert not report.compliant
    assert report.section == "09 68 13"
    assert report.by_status(FindingStatus.MISSING)
