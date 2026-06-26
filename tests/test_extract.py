from speccheck.extract import extract_requirements, find_section
from speccheck.models import RequirementKind


def test_find_section():
    assert find_section("SECTION 09 68 13 - TILE CARPETING") == "09 68 13"
    assert find_section("no section here") == ""


def test_extracts_standards():
    text = "Carpet tile shall comply with ASTM E648 and ASTM E662."
    reqs = extract_requirements(text)
    stds = {r.keyword for r in reqs if r.kind is RequirementKind.STANDARD}
    assert "ASTM E648" in stds
    assert "ASTM E662" in stds


def test_extracts_submittal_items():
    text = "Submit product data for each type of carpet tile."
    reqs = extract_requirements(text)
    items = {r.keyword for r in reqs if r.kind is RequirementKind.SUBMITTAL_ITEM}
    assert "product data" in items


def test_extracts_numeric_with_bound():
    text = "Provide carpet tile with a minimum pile height of 0.27 inch."
    reqs = extract_requirements(text)
    numeric = [r for r in reqs if r.kind is RequirementKind.NUMERIC]
    assert numeric
    r = numeric[0]
    assert r.quantity == 0.27
    assert r.unit == "inch"
    assert r.bound == "min"


def test_fraction_normalized():
    reqs = extract_requirements("Joint width shall be 3/8 inch minimum.")
    numeric = [r for r in reqs if r.kind is RequirementKind.NUMERIC]
    assert numeric
    assert abs(numeric[0].quantity - 0.375) < 1e-6
