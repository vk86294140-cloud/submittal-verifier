"""Requirement extraction from specification text.

The extractor is deliberately rule-based: construction specs follow strong
conventions (CSI three-part format, imperative "shall" language, referenced
consensus standards), so a handful of well-chosen patterns recover most
checkable obligations without a model. The optional LLM pass in ``llm.py``
layers semantic requirements on top of this baseline.
"""

from __future__ import annotations

import re

from .models import Requirement, RequirementKind

# ASTM E84, ANSI/BHMA A156.2, ISO 9001, UL 263, NFPA 70, FS ... etc.
STANDARD_RE = re.compile(
    r"\b(?:ASTM|ANSI|BHMA|ISO|UL|NFPA|FS|AAMA|SAE|AWS|ACI|AISC|ASHRAE|FM)"
    r"(?:/[A-Z]+)?\s?[A-Z]?-?\d[\w.\-/]*",
)

# "Submit product data ...", "Submittals: Shop Drawings ..."
SUBMIT_RE = re.compile(r"\bsubmit(?:tal)?s?\b", re.IGNORECASE)

# 0.27 inch, 3/8", 45 psf, 1.5 in, 90 percent, 1/2 inch
NUM_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?(?:\s*/\s*\d+)?)\s*"
    r"(?P<unit>inch(?:es)?|in\.?|\"|ft|feet|psf|psi|lb(?:s)?|percent|%|mm|cm|gauge|ga)\b",
    re.IGNORECASE,
)

BOUND_WORDS = {
    "min": ("minimum", "not less than", "at least", "no less than"),
    "max": ("maximum", "not more than", "no more than", "not to exceed"),
}

# Section header e.g. "SECTION 09 68 13 - TILE CARPETING" or "09 68 13"
SECTION_RE = re.compile(r"\b(\d{2}\s?\d{2}\s?\d{2})\b")

SENTENCE_SPLIT = re.compile(r"(?<=[.:;])\s+(?=[A-Z0-9])")

# Words with no discriminating power when binding a numeric requirement to a
# submitted value. Units and boilerplate verbs/quantifiers live here so that
# keyword matching turns on real nouns ("pile height") not filler ("provide").
STOPWORDS = {
    "inch", "inches", "in", "ft", "feet", "foot", "psf", "psi", "lb", "lbs",
    "percent", "gauge", "ga", "mm", "cm", "watts", "ounce", "kilovolts",
    "provide", "submit", "shall", "must", "with", "each", "type", "the", "and",
    "for", "not", "less", "than", "more", "minimum", "maximum", "nominal",
    "two", "all", "from", "per", "square", "centimeter", "yard",
}


def content_words(text: str) -> set[str]:
    """Discriminating lowercase tokens from a phrase (drops units/filler)."""
    return {
        w for w in re.findall(r"[a-z]+", text.lower())
        if len(w) > 2 and w not in STOPWORDS
    }


def _normalize_num(token: str) -> float | None:
    token = token.strip()
    if "/" in token:
        try:
            num, den = (t.strip() for t in token.split("/"))
            return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(token)
    except ValueError:
        return None


def _detect_bound(text: str) -> str:
    low = text.lower()
    for bound, words in BOUND_WORDS.items():
        if any(w in low for w in words):
            return bound
    return "exact"


def find_section(text: str) -> str:
    m = SECTION_RE.search(text)
    if not m:
        return ""
    digits = re.sub(r"\s+", "", m.group(1))
    return f"{digits[0:2]} {digits[2:4]} {digits[4:6]}"


def extract_requirements(text: str) -> list[Requirement]:
    """Pull checkable requirements out of raw spec text."""
    section = find_section(text)
    reqs: list[Requirement] = []
    seen: set[tuple] = set()

    def add(req: Requirement) -> None:
        # For numerics, dedupe on the value itself so a dimension pair like
        # "24 inch by 24 inch" yields one requirement, not two.
        if req.kind is RequirementKind.NUMERIC:
            key = (req.kind, req.quantity, req.unit, req.bound, req.text[:60])
        else:
            key = (req.kind, req.keyword, req.quantity, req.text[:60])
        if key not in seen:
            seen.add(key)
            req.section = section
            reqs.append(req)

    for sentence in _split_sentences(text):
        clause = sentence.strip()
        if not clause:
            continue

        # 1) Referenced standards -> one STANDARD requirement per citation.
        for m in STANDARD_RE.finditer(clause):
            std = re.sub(r"\s+", " ", m.group()).strip().rstrip(".,;")
            add(Requirement(RequirementKind.STANDARD, clause, keyword=std))

        # 2) Required submittal items.
        if SUBMIT_RE.search(clause):
            item = _submittal_item_label(clause)
            if item:
                add(Requirement(RequirementKind.SUBMITTAL_ITEM, clause,
                                keyword=item))

        # 3) Numeric thresholds (skip if the only numbers were section codes).
        for m in NUM_RE.finditer(clause):
            value = _normalize_num(m.group("num"))
            if value is None:
                continue
            add(Requirement(
                RequirementKind.NUMERIC, clause,
                keyword=_numeric_keyword(clause, m.start()),
                quantity=value, unit=_canon_unit(m.group("unit")),
                bound=_detect_bound(clause),
            ))

        # 4) Residual "shall/must" clauses we could not structure.
        if re.search(r"\b(shall|must|required to)\b", clause, re.IGNORECASE):
            if not any(r.text == clause for r in reqs):
                add(Requirement(RequirementKind.GENERAL, clause))

    return reqs


def _split_sentences(text: str) -> list[str]:
    # Specs are line- and clause-oriented; split on newlines first, then
    # on sentence punctuation so list items survive intact.
    lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.extend(SENTENCE_SPLIT.split(line))
    return lines


def _submittal_item_label(clause: str) -> str:
    """Turn 'Submit product data for adhesive.' -> 'product data'."""
    low = clause.lower()
    for kind in ("shop drawing", "product data", "sample", "test report",
                 "certificate", "warranty", "maintenance data",
                 "leed", "calculation", "mock-up", "mockup"):
        if kind in low:
            return kind
    # Fallback: text after the verb "submit" (word-bounded so a section
    # heading like "1.2 SUBMITTALS" is not mistaken for a deliverable).
    m = re.search(r"\bsubmit\b\s*:?\s*(.+)", clause, re.IGNORECASE)
    if not m:
        return ""
    cand = m.group(1).strip().rstrip(".").lower()
    return cand[:40] if len(cand) >= 4 else ""


def _numeric_keyword(clause: str, pos: int) -> str:
    """Grab the noun phrase preceding a number, e.g. 'pile height'.

    Returns only discriminating words; if nothing meaningful precedes the
    number the requirement stays unbound and is reported as UNVERIFIED rather
    than guessed against an unrelated value.
    """
    before = clause[:pos].strip().rstrip(":-").split()
    window = " ".join(before[-4:])
    words = [w for w in re.findall(r"[a-z]+", window.lower())
             if len(w) > 2 and w not in STOPWORDS]
    return " ".join(words[-3:])


def _canon_unit(unit: str) -> str:
    u = unit.lower().strip(". ")
    return {
        '"': "inch", "in": "inch", "inches": "inch",
        "ft": "feet", "%": "percent", "ga": "gauge",
    }.get(u, u)
