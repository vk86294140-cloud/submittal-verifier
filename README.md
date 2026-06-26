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
python -m pytest            # core suite runs offline, no extra installs
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

### Web app (multi-user)

A browser tool where reviewers upload a spec + submittal, get a saved shareable
review, and see a dashboard of past decisions. Resubmittals link to the round
they supersede.

```bash
pip install -e ".[web,pdf]"
uvicorn speccheck.web:app --host 0.0.0.0 --port 8000
# open http://127.0.0.1:8000
```

Endpoints: `/` dashboard + upload, `/reviews/{id}` saved review,
`/reviews/{id}/report.{html,json}` downloads, `/api/verify` stateless JSON,
`/healthz` probe.

| Env var | Purpose |
| --- | --- |
| `SPECCHECK_PASSWORD` | enable HTTP Basic auth (set this for any non-trusted network) |
| `SPECCHECK_USER` | auth username (default `admin`) |
| `SPECCHECK_DB` | SQLite path (default `./speccheck.db`) |

## Deploy (let another laptop use it)

The same app serves three ways — pick by who needs to reach it.

**A — Office LAN.** Run on one machine; coworkers open `http://<your-ip>:8000`.
```bash
pip install -e ".[web,pdf]"
SPECCHECK_PASSWORD=changeme uvicorn speccheck.web:app --host 0.0.0.0 --port 8000
# find <your-ip> with `ipconfig` (Windows) / `ip addr` (Linux); allow port 8000 in the firewall
```

**B — Cloud public URL (Render).** Push this repo, then in Render: *New → Blueprint*
and pick the repo — it reads [`render.yaml`](render.yaml). Set `SPECCHECK_PASSWORD`
in the dashboard. You get `https://<name>.onrender.com`. (Railway/Fly work the
same via the `Dockerfile`.)

**C — Docker (any server/VPS).**
```bash
docker build -t speccheck .
docker run -p 8000:8000 -e SPECCHECK_PASSWORD=changeme \
  -v "$PWD/data:/data" -e SPECCHECK_DB=/data/speccheck.db speccheck
```
The `-v` volume keeps the review database across restarts.

> The app stores construction submittals. For anything beyond a trusted LAN,
> always set `SPECCHECK_PASSWORD` and serve over HTTPS (Render/Fly terminate TLS
> for you).

## Project layout

```
speccheck/
  models.py      domain types (Requirement, Finding, Report)
  extract.py     spec  -> requirements   (rule-based)
  verify.py      submittal parse + cross-reference engine
  llm.py         optional Claude enrichment (best-effort, additive)
  report.py      text / JSON / HTML renderers
  store.py       SQLite audit trail of past reviews
  resubmittal.py diff a submittal against a prior saved review
  cli.py         command-line interface
  web.py         FastAPI web app: dashboard, upload, auth, JSON API
samples/         a real-format spec section 09 68 13 and a submittal
tests/           pytest suite (core offline; web tests skip without FastAPI)
Dockerfile · render.yaml · Procfile   deploy to a container / Render / PaaS
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
