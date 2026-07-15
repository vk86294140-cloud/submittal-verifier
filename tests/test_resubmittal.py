from speccheck import diff_reviews, extract_requirements, parse_submittal, verify
from speccheck.report import to_dict
from speccheck.resubmittal import render

SPEC = (
    "Submit test reports from an independent agency. "
    "Minimum pile height of 0.27 inch. "
    "Comply with ASTM E662 for smoke density."
)


def _report(submittal_text):
    return verify(extract_requirements(SPEC), parse_submittal(submittal_text))


def test_clears_and_recurs():
    # Round 1: nothing supplied -> all three requirements blocking.
    round1 = _report("Product data only. Pile height: 0.20 inch.")
    prior = to_dict(round1)["findings"]

    # Round 2: test report added and pile height fixed, ASTM still wrong.
    round2 = _report("Test report enclosed. Pile height: 0.30 inch. Tested to ASTM E84.")
    d = diff_reviews(prior, round2)

    cleared = " ".join(d.cleared).lower()
    assert "test report" in cleared
    assert any("pile height" in c.lower() for c in d.cleared)
    assert any("E662" in r for r in d.recurring)
    assert not d.resolved_all


def test_resolved_all_when_clean():
    round1 = _report("Product data only. Pile height: 0.20 inch.")
    prior = to_dict(round1)["findings"]
    fixed = _report("Test report enclosed. Pile height: 0.30 inch. Complies with ASTM E662.")
    d = diff_reviews(prior, fixed)
    assert d.resolved_all
    assert not d.recurring and not d.new


def test_render_lists_buckets():
    d = diff_reviews(to_dict(_report("Product data only."))["findings"], _report("Product data only."))
    text = render(d)
    assert "Recurring" in text and "Cleared" in text and "New" in text
