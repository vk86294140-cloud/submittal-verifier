"""speccheck — automated construction submittal verification.

Cross-references a contractor submittal against the project specification
section and reports what is met, missing, or deviating.
"""

from __future__ import annotations

from .extract import extract_requirements
from .llm import enrich
from .models import Finding, FindingStatus, Report, Requirement, SubmittalDoc
from .parse_pdf import load_text
from .report import to_dict, to_html, to_json, to_text
from .resubmittal import ResubmittalDiff
from .resubmittal import diff as diff_reviews
from .verify import parse_submittal, verify

__version__ = "0.1.0"

__all__ = [
    "review",
    "extract_requirements",
    "enrich",
    "parse_submittal",
    "verify",
    "diff_reviews",
    "ResubmittalDiff",
    "load_text",
    "to_dict",
    "to_html",
    "to_json",
    "to_text",
    "Report",
    "Requirement",
    "Finding",
    "FindingStatus",
    "SubmittalDoc",
]


def review(spec_text: str, submittal_text: str, use_llm: bool = False) -> Report:
    """End-to-end: extract spec requirements, parse submittal, verify.

    When ``use_llm`` is True and an API key is configured, semantic
    requirements from Claude are merged with the rule-based baseline.
    """
    requirements = extract_requirements(spec_text)
    if use_llm:
        requirements.extend(enrich(spec_text))
    submittal = parse_submittal(submittal_text)
    return verify(requirements, submittal)
