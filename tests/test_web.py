"""Web app tests. Skipped automatically if FastAPI/httpx aren't installed."""

import importlib
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECCHECK_DB", str(tmp_path / "test.db"))
    monkeypatch.delenv("SPECCHECK_PASSWORD", raising=False)
    import speccheck.web as web

    importlib.reload(web)  # pick up the patched SPECCHECK_DB
    return TestClient(web.app)


def _files():
    return {
        "spec": ("spec.txt", (SAMPLES / "spec_096813.txt").read_bytes(), "text/plain"),
        "submittal": ("sub.txt", (SAMPLES / "submittal_096813.txt").read_bytes(), "text/plain"),
    }


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_dashboard_empty(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "No reviews yet" in r.text


def test_upload_creates_and_views_review(client):
    r = client.post("/reviews", files=_files(), data={"project": "Riverside"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Review #1" in r.text
    assert "REVISE" in r.text  # sample submittal is non-compliant
    assert "Riverside" in r.text
    # now appears on the dashboard
    assert "Riverside" in client.get("/").text


def test_download_json(client):
    client.post("/reviews", files=_files(), data={"project": "P"})
    body = client.get("/reviews/1/report.json").json()
    assert body["section"] == "09 68 13"
    assert body["compliant"] is False


def test_resubmittal_links_prior(client):
    client.post("/reviews", files=_files(), data={"project": "P"})
    fixed = (SAMPLES / "submittal_096813.txt").read_text().replace("0.20 inch", "0.30 inch")
    files = {
        "spec": ("spec.txt", (SAMPLES / "spec_096813.txt").read_bytes(), "text/plain"),
        "submittal": ("sub2.txt", fixed.encode(), "text/plain"),
    }
    r = client.post("/reviews", files=files, data={"project": "P", "prior_id": "1"}, follow_redirects=True)
    assert "Resubmittal vs review #1" in r.text
    assert "Cleared" in r.text


def test_api_verify(client):
    r = client.post("/api/verify", files=_files())
    assert r.status_code == 200
    assert r.json()["section"] == "09 68 13"


def test_auth_required_when_password_set(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECCHECK_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("SPECCHECK_PASSWORD", "s3cret")
    monkeypatch.setenv("SPECCHECK_USER", "boss")
    import speccheck.web as web

    importlib.reload(web)
    c = TestClient(web.app)
    assert c.get("/").status_code == 401
    assert c.get("/", auth=("boss", "s3cret")).status_code == 200
    # /healthz stays open for load-balancer probes
    assert c.get("/healthz").status_code == 200


def test_security_headers_present(client):
    h = client.get("/").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert "content-security-policy" in h


def test_rejects_non_allowed_extension(client):
    files = {
        "spec": ("spec.exe", b"malware", "application/octet-stream"),
        "submittal": ("sub.txt", b"data", "text/plain"),
    }
    assert client.post("/reviews", files=files).status_code == 400


def test_rejects_oversized_upload(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECCHECK_DB", str(tmp_path / "big.db"))
    monkeypatch.setenv("SPECCHECK_MAX_UPLOAD_MB", "1")
    monkeypatch.delenv("SPECCHECK_PASSWORD", raising=False)
    import speccheck.web as web

    importlib.reload(web)
    c = TestClient(web.app)
    big = b"x" * (2 * 1024 * 1024)  # 2 MB > 1 MB cap
    files = {
        "spec": ("spec.txt", big, "text/plain"),
        "submittal": ("sub.txt", b"data", "text/plain"),
    }
    assert c.post("/reviews", files=files).status_code == 413


def test_rate_limit_returns_429(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECCHECK_DB", str(tmp_path / "rl.db"))
    monkeypatch.setenv("SPECCHECK_RATE_LIMIT", "3")
    monkeypatch.delenv("SPECCHECK_PASSWORD", raising=False)
    import speccheck.web as web

    importlib.reload(web)
    c = TestClient(web.app)
    codes = [c.get("/").status_code for _ in range(5)]
    assert 429 in codes
    # health checks bypass the limiter
    assert c.get("/healthz").status_code == 200
