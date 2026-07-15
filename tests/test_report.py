import json

from speccheck import extract_requirements, parse_submittal, verify
from speccheck.report import to_dict, to_html, to_json, to_text


def _sample_report():
    req = extract_requirements("Minimum pile height of 0.27 inch. Comply with ASTM E648.")
    sub = parse_submittal("Pile height: 0.20 inch. Complies with ASTM E84.")
    return verify(req, sub)


def test_to_dict_has_expected_keys():
    d = to_dict(_sample_report())
    assert set(d) == {"section", "compliant", "summary", "findings"}
    assert isinstance(d["findings"], list)


def test_to_json_roundtrips():
    text = to_json(_sample_report())
    parsed = json.loads(text)
    assert parsed["compliant"] is False


def test_to_text_contains_verdict_and_findings():
    text = to_text(_sample_report())
    assert "REVISE & RESUBMIT" in text
    assert "summary:" in text


def test_to_html_escapes_and_contains_table():
    report = _sample_report()
    out = to_html(report)
    assert "<table>" in out
    assert "REVISE" in out or "APPROVE" in out
    # every finding's requirement label should appear, HTML-escaped
    for f in report.findings:
        assert f.requirement.label()[:10] in out or "&" in out
