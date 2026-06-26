# speccheck — construction submittal verification

Automated cross-referencing of a contractor **submittal** against the project
**specification**. It reads a CSI MasterFormat spec section and the contractor's
submittal, then reports — clause by clause — what is **met**, **missing**,
**deviating**, or needs **manual review**, so a reviewer stops reading two
documents in parallel and starts from a decision-ready compliance matrix.

> In construction, every product a contractor installs must first be approved
> via a submittal (product data, shop drawings, samples, test reports) checked
> against the spec. On a large project that is thousands of manual line-by-line
> comparisons. `speccheck` does the mechanical pass and surfaces only what a
> human needs to judge.

## What it checks

| Finding | Meaning |
| --- | --- |
| `MET` | Requirement satisfied by the submittal |
| `MISSING` | A required submittal item or referenced standard is absent |
| `STANDARD_MISMATCH` | Spec cites e.g. `ASTM E662`; submittal cites a different standard in the same family |
| `VALUE_DEVIATION` | A submitted dimension/value violates a spec minimum/maximum |
| `UNVERIFIED` | Parsed but not auto-checkable — flagged for manual review |

The verdict is binary and conservative: **APPROVE** only when nothing is
missing or deviating; otherwise **REVISE & RESUBMIT**.

## How it works

```
spec text ─▶ extract_requirements ─┐
                                    ├─▶ verify ─▶ Report ─▶ text / JSON / HTML
submittal text ─▶ parse_submittal ─┘
```

Extraction is **rule-based** by design — construction specs follow strong
conventions (CSI three-part format, imperative "shall" language, referenced
consensus standards), so targeted patterns recover most checkable obligations
deterministically and offline. An **optional** Claude pass (`--llm`) adds
semantic requirements the regexes miss; it is strictly additive and degrades to
the offline baseline when no API key is present.

## Install

No third-party packages are needed for the core library, CLI, and tests.

```bash
git clone https://github.com/vk86294140-cloud/submittal-verifier
cd submittal-verifier
python -m pytest            # 11 tests, runs offline
```

Optional extras:

```bash
pip install -e ".[pdf]"     # verify .pdf files (pdfplumber)
pip install -e ".[web]"     # FastAPI upload UI
pip install -e ".[llm]"     # Claude semantic enrichment
```

## Use

### CLI

```bash
# Plain-text verdict (exit code 2 when the submittal must be revised)
python -m speccheck.cli verify samples/spec_096813.txt samples/submittal_096813.txt

# Machine-readable / shareable outputs
python -m speccheck.cli verify spec.pdf submittal.pdf --format json
python -m speccheck.cli verify spec.txt submittal.txt --format html -o review.html

# Add Claude enrichment and persist the result to speccheck.db
python -m speccheck.cli verify spec.txt submittal.txt --llm --save
python -m speccheck.cli history

# Resubmittal: diff a new round against a prior saved review
python -m speccheck.cli verify spec.txt resubmittal.txt --against 1
```

### Resubmittal tracking

After a "revise and resubmit", save the first review (`--save`), then verify the
next round with `--against <review_id>`. The diff sorts blocking findings into
**cleared** (fixed), **recurring** (still open), and **new** (regressions):

```
Resubmittal diff — Section 09 68 13: OUTSTANDING ISSUES REMAIN
  Cleared (1):
    - pile height >= 0.27 inch
  Recurring (3):
    - Comply with ASTM E662
    - Submit certified test reports ...
    - Submit maintenance data ...
  New (0):
    (none)
```

Running the bundled sample produces:

```
Section 09 68 13 — REVISE & RESUBMIT
summary: missing=2, standard_mismatch=1, value_deviation=1, unverified=2, met=7
----------------------------------------------------------------
[MISSING           ] Required submittal item 'test report' not found.
[MISSING           ] Required submittal item 'maintenance data' not found.
[STANDARD MISMATCH ] Spec requires ASTM E662; submittal cites ASTM E648, ASTM E84.
[VALUE DEVIATION   ] Submitted 0.2 inch violates pile height >= 0.27 inch.
...
```

An example HTML compliance matrix is checked in at
[`docs/example_report.html`](docs/example_report.html).

### Library

```python
from speccheck import review, to_html

report = review(spec_text, submittal_text)
print(report.compliant)          # False
print(report.summary())          # {'missing': 2, 'met': 7, ...}
open("review.html", "w").write(to_html(report))
```

### Web

```bash
pip install -e ".[web]"
uvicorn speccheck.web:app --reload
# open http://127.0.0.1:8000  — paste a spec + submittal, get the matrix
# POST /api/verify accepts spec/submittal file uploads and returns JSON
```

## Project layout

```
speccheck/
  models.py      domain types (Requirement, Finding, Report)
  extract.py     spec  -> requirements   (rule-based)
  verify.py      submittal parse + cross-reference engine
  llm.py         optional Claude enrichment (best-effort, additive)
  report.py      text / JSON / HTML renderers
  store.py       SQLite audit trail of past reviews
  cli.py         command-line interface
  web.py         FastAPI upload UI + JSON API
samples/         a real-format spec section 09 68 13 and a submittal
tests/           pytest suite (offline)
```

## Scope and limitations

- Targets text-extractable specs/submittals. Scanned drawings need OCR upstream.
- Numeric checks bind on a shared subject noun; ambiguous values are reported
  `UNVERIFIED` rather than guessed — false negatives are preferred over false
  approvals.
- The tool assists a reviewer; it does not replace the architect's stamp.

## Roadmap

- Spec-section auto-splitting for multi-section PDFs
- Submittal-item synonym dictionary loaded from a project's submittal register
- Side-by-side spec/submittal diff view in the web UI
- Resubmittal diff surfaced in the HTML report and web UI (currently CLI-only)

## License

MIT
