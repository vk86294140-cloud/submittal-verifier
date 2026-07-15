# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Ruff lint/format CI gate
- Mypy strict type-check CI gate
- pytest-cov with 90% coverage floor (74% -> 93%): new direct tests for `cli.py`,
  `llm.py` (mocked Anthropic client), `parse_pdf.py` (mocked pdfplumber), and
  `report.py`
- Dependabot config for pip and GitHub Actions updates

### Fixed
- Removed unused `typing.Optional` import/usage in `models.py` in favor of `X | None`
- Various mypy-strict findings: missing generic type parameters, untyped
  FastAPI middleware signature, `int | None` from `sqlite3.lastrowid`

## [0.2.0]

Prior history not tracked in this file.
