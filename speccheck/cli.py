"""Command-line interface.

    speccheck verify SPEC SUBMITTAL [--format text|json|html] [--llm] [--save]
    speccheck history
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, enrich, extract_requirements, parse_submittal, verify
from .parse_pdf import load_text
from .report import to_html, to_json, to_text
from .resubmittal import diff as diff_reviews
from .resubmittal import render as render_diff
from .store import get_review, list_reviews, save_review


def _cmd_verify(args: argparse.Namespace) -> int:
    spec_text = load_text(args.spec)
    submittal_text = load_text(args.submittal)

    requirements = extract_requirements(spec_text)
    if args.llm:
        added = enrich(spec_text)
        requirements.extend(added)
        print(f"# llm enrichment added {len(added)} requirement(s)",
              file=sys.stderr)
    if not requirements:
        print("warning: no requirements extracted from spec", file=sys.stderr)

    submittal = parse_submittal(submittal_text)
    report = verify(requirements, submittal)

    if args.against is not None:
        prior = get_review(args.against)
        if prior is None:
            print(f"error: no saved review #{args.against} "
                  f"(see 'speccheck history')", file=sys.stderr)
            return 1
        d = diff_reviews(prior["findings"], report)
        print(render_diff(d), file=sys.stderr)
        print("-" * 64, file=sys.stderr)

    if args.format == "json":
        out = to_json(report)
    elif args.format == "html":
        out = to_html(report)
    else:
        out = to_text(report)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(out)

    if args.save:
        rid = save_review(report)
        print(f"# saved review #{rid}", file=sys.stderr)

    # Non-zero exit when the submittal should be revised — handy in CI/scripts.
    return 0 if report.compliant else 2


def _cmd_history(_: argparse.Namespace) -> int:
    rows = list_reviews()
    if not rows:
        print("no reviews recorded")
        return 0
    for r in rows:
        verdict = "APPROVE" if r["compliant"] else "REVISE"
        print(f"#{r['id']:>3}  {r['created_at']}  {r['section']:<10}  "
              f"{verdict}  {r['summary']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="speccheck",
        description="Verify a construction submittal against the project spec.",
    )
    p.add_argument("--version", action="version",
                   version=f"speccheck {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("verify", help="verify a submittal against a spec")
    v.add_argument("spec", help="spec section file (.txt or .pdf)")
    v.add_argument("submittal", help="submittal file (.txt or .pdf)")
    v.add_argument("--format", choices=("text", "json", "html"),
                   default="text")
    v.add_argument("--output", "-o", help="write report to file instead of stdout")
    v.add_argument("--llm", action="store_true",
                   help="add Claude semantic enrichment (needs ANTHROPIC_API_KEY)")
    v.add_argument("--save", action="store_true",
                   help="persist the review to speccheck.db")
    v.add_argument("--against", type=int, metavar="REVIEW_ID",
                   help="diff this submittal against a prior saved review")
    v.set_defaults(func=_cmd_verify)

    h = sub.add_parser("history", help="list saved reviews")
    h.set_defaults(func=_cmd_history)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
