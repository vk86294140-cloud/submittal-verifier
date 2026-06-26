"""Web application — multi-user submittal verification.

A reviewer opens the app in a browser, uploads a spec section and a contractor
submittal (``.txt`` or ``.pdf``), and gets a saved, shareable compliance
review. Past reviews are listed on the dashboard; a resubmittal can be linked
to the round it supersedes so only what changed is highlighted.

Run locally / on a LAN:
    python -m uvicorn speccheck.web:app --host 0.0.0.0 --port 8000

Security-relevant environment variables:
    SPECCHECK_PASSWORD     require HTTP Basic auth (set for any non-trusted net)
    SPECCHECK_USER         auth username (default "admin")
    SPECCHECK_DB           SQLite path (default "speccheck.db")
    SPECCHECK_MAX_UPLOAD_MB per-file upload cap in MB (default 10)
    SPECCHECK_RATE_LIMIT   requests/min per client IP, 0 disables (default 120)
"""

from __future__ import annotations

import html
import os
import secrets
import time
from collections import defaultdict, deque

try:
    from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile, status
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
    from fastapi.security import HTTPBasic, HTTPBasicCredentials
except ImportError as exc:  # pragma: no cover - optional dependency
    raise RuntimeError(
        "The web app needs FastAPI. Install: pip install fastapi uvicorn python-multipart"
    ) from exc

from . import extract_requirements, parse_submittal, verify
from .parse_pdf import load_text_bytes
from .report import to_dict, to_html, to_json
from .resubmittal import diff as diff_reviews
from .resubmittal import render as render_diff
from .store import get_review, list_reviews, save_review

DB_PATH = os.environ.get("SPECCHECK_DB", "speccheck.db")
MAX_UPLOAD_BYTES = int(os.environ.get("SPECCHECK_MAX_UPLOAD_MB", "10")) * 1024 * 1024
RATE_LIMIT_PER_MIN = int(os.environ.get("SPECCHECK_RATE_LIMIT", "120"))
ALLOWED_EXT = (".txt", ".pdf")

app = FastAPI(title="speccheck", version="0.2.0")
_security = HTTPBasic(auto_error=False)

# Per-client request timestamps for the in-memory rate limiter. This is
# per-process: a single instance is protected; running multiple replicas
# behind a load balancer needs a shared store (Redis) instead.
_request_log: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Throttle abusive clients and attach hardening headers to every response."""
    if RATE_LIMIT_PER_MIN > 0 and request.url.path != "/healthz":
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = _request_log[client_ip]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= RATE_LIMIT_PER_MIN:
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        hits.append(now)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


async def _read_upload(file: UploadFile) -> tuple[str, bytes]:
    """Validate an uploaded file's type and size before it is parsed.

    Only ``.txt`` and ``.pdf`` are accepted, and a per-file byte cap bounds
    memory use and blocks decompression/parser abuse from oversized PDFs.
    """
    name = file.filename or ""
    if not name.lower().endswith(ALLOWED_EXT):
        raise HTTPException(status_code=400,
                            detail="Only .txt or .pdf files are accepted")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
    return name, data


def require_auth(creds: HTTPBasicCredentials | None = Depends(_security)) -> None:
    """Enforce HTTP Basic auth when SPECCHECK_PASSWORD is set; open otherwise."""
    password = os.environ.get("SPECCHECK_PASSWORD")
    if not password:
        return
    user = os.environ.get("SPECCHECK_USER", "admin")
    ok = creds is not None and secrets.compare_digest(creds.username, user) \
        and secrets.compare_digest(creds.password, password)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )


# ── rendering helpers ─────────────────────────────────────────────────────

_STYLE = """
 body{font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;
      margin:2rem auto;padding:0 1rem;color:#1f2328}
 a{color:#1f6feb;text-decoration:none}a:hover{text-decoration:underline}
 h1{font-size:1.4rem}.muted{color:#656d76}
 table{border-collapse:collapse;width:100%;margin:1rem 0}
 th,td{text-align:left;padding:.45rem .6rem;border-bottom:1px solid #d0d7de}
 th{background:#f6f8fa;font-size:.78rem;text-transform:uppercase;letter-spacing:.03em}
 .pill{padding:.1rem .55rem;border-radius:.7rem;color:#fff;font-size:.74rem}
 .ok{background:#1a7f37}.bad{background:#cf222e}
 .card{border:1px solid #d0d7de;border-radius:.5rem;padding:1.2rem;margin:1rem 0}
 label{font-weight:600;display:block;margin:.7rem 0 .25rem}
 input[type=text],input[type=number]{width:100%;padding:.45rem;border:1px solid #d0d7de;border-radius:.3rem}
 button{background:#1f6feb;color:#fff;border:0;padding:.6rem 1.2rem;border-radius:.4rem;
        font-size:1rem;cursor:pointer;margin-top:1rem}
 nav{margin-bottom:1.5rem}pre{background:#f6f8fa;padding:.8rem;border-radius:.4rem;overflow:auto}
"""


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head>"
            f"<body><nav><a href='/'>&larr; speccheck dashboard</a></nav>{body}</body></html>")


def _verdict_pill(compliant: bool) -> str:
    return ('<span class="pill ok">APPROVE</span>' if compliant
            else '<span class="pill bad">REVISE</span>')


# ── routes ────────────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard(_: None = Depends(require_auth)) -> str:
    rows = list_reviews(DB_PATH)
    if rows:
        items = "".join(
            f"<tr><td><a href='/reviews/{r['id']}'>#{r['id']}</a></td>"
            f"<td>{html.escape(r['project'] or '—')}</td>"
            f"<td>{html.escape(r['section'] or '—')}</td>"
            f"<td>{_verdict_pill(bool(r['compliant']))}</td>"
            f"<td class='muted'>{html.escape(r['created_at'])}</td>"
            f"<td>{('resubmittal of #' + str(r['prior_id'])) if r['prior_id'] else ''}</td></tr>"
            for r in rows
        )
        table = ("<table><thead><tr><th>ID</th><th>Project</th><th>Section</th>"
                 "<th>Verdict</th><th>Reviewed</th><th>Note</th></tr></thead>"
                 f"<tbody>{items}</tbody></table>")
    else:
        table = "<p class='muted'>No reviews yet. Upload a spec and submittal below.</p>"

    form = """
    <div class="card"><h2 style="margin-top:0;font-size:1.1rem">New verification</h2>
    <form method="post" action="/reviews" enctype="multipart/form-data">
      <label>Project name</label>
      <input type="text" name="project" placeholder="Riverside Medical Office Building">
      <label>Specification section (.txt or .pdf)</label>
      <input type="file" name="spec" accept=".txt,.pdf" required>
      <label>Submittal (.txt or .pdf)</label>
      <input type="file" name="submittal" accept=".txt,.pdf" required>
      <label>Resubmittal of review # (optional)</label>
      <input type="number" name="prior_id" placeholder="leave blank for a first submission">
      <button type="submit">Verify &amp; save</button>
    </form></div>"""

    return _page("speccheck dashboard",
                 f"<h1>Submittal verification</h1>{form}<h2 style='font-size:1.1rem'>"
                 f"Reviews</h2>{table}")


@app.post("/reviews")
async def create_review(
    spec: UploadFile,
    submittal: UploadFile,
    project: str = Form(""),
    prior_id: str = Form(""),
    _: None = Depends(require_auth),
) -> RedirectResponse:
    spec_name, spec_data = await _read_upload(spec)
    sub_name, sub_data = await _read_upload(submittal)
    spec_text = load_text_bytes(spec_name, spec_data)
    sub_text = load_text_bytes(sub_name, sub_data)
    report = verify(extract_requirements(spec_text), parse_submittal(sub_text))

    prior = int(prior_id) if prior_id.strip().isdigit() else None
    review_id = save_review(
        report, DB_PATH, project=project.strip(),
        spec_text=spec_text, submittal_text=sub_text, prior_id=prior,
    )
    return RedirectResponse(f"/reviews/{review_id}",
                            status_code=status.HTTP_303_SEE_OTHER)


@app.get("/reviews/{review_id}", response_class=HTMLResponse)
def view_review(review_id: int, _: None = Depends(require_auth)) -> str:
    rec = get_review(review_id, DB_PATH)
    if rec is None:
        raise HTTPException(status_code=404, detail="review not found")

    header = (f"<h1>Review #{rec['id']} {_verdict_pill(bool(rec['compliant']))}</h1>"
              f"<p class='muted'>{html.escape(rec['project'] or 'Untitled project')} · "
              f"Section {html.escape(rec['section'] or 'N/A')} · {html.escape(rec['created_at'])}</p>"
              f"<p><a href='/reviews/{rec['id']}/report.html'>Download HTML</a> · "
              f"<a href='/reviews/{rec['id']}/report.json'>Download JSON</a></p>")

    diff_html = ""
    if rec["prior_id"]:
        prior = get_review(int(rec["prior_id"]), DB_PATH)
        if prior:
            d = diff_reviews(prior["findings"], _report_from(rec))
            diff_html = (f"<div class='card'><h2 style='margin-top:0;font-size:1.1rem'>"
                         f"Resubmittal vs review #{rec['prior_id']}</h2>"
                         f"<pre>{html.escape(render_diff(d))}</pre></div>")

    rows = "".join(
        f"<tr><td>{_finding_pill(f['status'])}</td>"
        f"<td>{html.escape(f['requirement'])}</td>"
        f"<td class='muted'>{html.escape(f['detail'])}</td></tr>"
        for f in rec["findings"]
    )
    matrix = ("<table><thead><tr><th>Status</th><th>Requirement</th><th>Detail</th>"
              f"</tr></thead><tbody>{rows}</tbody></table>")
    return _page(f"Review #{rec['id']}", header + diff_html + matrix)


@app.get("/reviews/{review_id}/report.html")
def download_html(review_id: int, _: None = Depends(require_auth)) -> Response:
    rec = get_review(review_id, DB_PATH)
    if rec is None:
        raise HTTPException(status_code=404, detail="review not found")
    return HTMLResponse(to_html(_report_from(rec)))


@app.get("/reviews/{review_id}/report.json")
def download_json(review_id: int, _: None = Depends(require_auth)) -> Response:
    rec = get_review(review_id, DB_PATH)
    if rec is None:
        raise HTTPException(status_code=404, detail="review not found")
    return Response(to_json(_report_from(rec)), media_type="application/json")


@app.post("/api/verify")
async def verify_api(spec: UploadFile, submittal: UploadFile,
                     _: None = Depends(require_auth)) -> JSONResponse:
    """Stateless JSON endpoint for scripting/integrations."""
    spec_name, spec_data = await _read_upload(spec)
    sub_name, sub_data = await _read_upload(submittal)
    spec_text = load_text_bytes(spec_name, spec_data)
    sub_text = load_text_bytes(sub_name, sub_data)
    report = verify(extract_requirements(spec_text), parse_submittal(sub_text))
    return JSONResponse(to_dict(report))


# ── helpers that rebuild a Report from a stored record ─────────────────────

def _report_from(rec: dict):
    """Re-verify from stored documents so renderers get a live Report object."""
    return verify(extract_requirements(rec["spec_text"]),
                  parse_submittal(rec["submittal_text"]))


_PILL_CLASS = {"met": "ok", "missing": "bad", "standard_mismatch": "bad",
               "value_deviation": "bad", "unverified": "muted"}


def _finding_pill(status_value: str) -> str:
    cls = _PILL_CLASS.get(status_value, "muted")
    label = status_value.replace("_", " ").upper()
    if cls == "muted":
        return f"<span class='muted'>{label}</span>"
    return f"<span class='pill {cls}'>{label}</span>"
