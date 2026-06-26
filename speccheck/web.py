"""Optional web interface (FastAPI).

Run:  uvicorn speccheck.web:app --reload
Then open http://127.0.0.1:8000 to upload a spec + submittal and view the
compliance matrix. Requires ``fastapi`` and ``uvicorn`` (see requirements.txt);
the core library and CLI work without them.
"""

from __future__ import annotations

try:
    from fastapi import FastAPI, Form, UploadFile
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError as exc:  # pragma: no cover - optional dependency
    raise RuntimeError(
        "The web interface needs FastAPI. Install: pip install fastapi uvicorn"
    ) from exc

from . import extract_requirements, parse_submittal, verify
from .report import to_dict, to_html

app = FastAPI(title="speccheck", version="0.1.0")

_UPLOAD_FORM = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>speccheck — submittal verifier</title>
<style>
 body{font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;max-width:640px;margin:3rem auto;color:#1f2328}
 h1{font-size:1.4rem}.field{margin:1rem 0}
 textarea{width:100%;min-height:8rem;font:13px/1.4 ui-monospace,monospace;padding:.5rem}
 label{font-weight:600;display:block;margin-bottom:.3rem}
 button{background:#1f6feb;color:#fff;border:0;padding:.6rem 1.2rem;border-radius:.4rem;font-size:1rem;cursor:pointer}
 .hint{color:#656d76;font-size:.85rem}
</style></head><body>
<h1>Submittal compliance check</h1>
<p class="hint">Paste the spec section and the contractor submittal, or use the
sample text. The checker reports what is met, missing, or deviating.</p>
<form method="post" action="/verify">
 <div class="field"><label>Specification section</label>
  <textarea name="spec" required placeholder="SECTION 09 68 13 ..."></textarea></div>
 <div class="field"><label>Submittal</label>
  <textarea name="submittal" required placeholder="Product Data ..."></textarea></div>
 <button type="submit">Verify</button>
</form></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _UPLOAD_FORM


@app.post("/verify", response_class=HTMLResponse)
def verify_form(spec: str = Form(...), submittal: str = Form(...)) -> str:
    report = verify(extract_requirements(spec), parse_submittal(submittal))
    return to_html(report)


@app.post("/api/verify")
async def verify_api(spec: UploadFile, submittal: UploadFile) -> JSONResponse:
    spec_text = (await spec.read()).decode("utf-8", "ignore")
    sub_text = (await submittal.read()).decode("utf-8", "ignore")
    report = verify(extract_requirements(spec_text), parse_submittal(sub_text))
    return JSONResponse(to_dict(report))
