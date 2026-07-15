"""Document loading.

Accepts ``.txt`` directly and ``.pdf`` when a PDF backend is installed.
Kept dependency-light: PDF support is optional so the tool and its tests run
without native libraries, while real-world PDFs still work when ``pdfplumber``
or ``pypdf`` is present.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import ModuleType


def load_text_bytes(filename: str, data: bytes) -> str:
    """Return the text of an uploaded file given its name and raw bytes.

    Routes ``.pdf`` through the PDF backend (via a temp file) and decodes
    everything else as UTF-8. Used by the web upload endpoints.
    """
    if filename.lower().endswith(".pdf"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            return _load_pdf(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)
    return data.decode("utf-8", errors="ignore")


def load_text(path: str | Path) -> str:
    """Return the plain text of a spec or submittal document."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".pdf":
        return _load_pdf(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_pdf(path: Path) -> str:
    pdfplumber: ModuleType | None
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None

    if pdfplumber is not None:
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "Reading PDF requires 'pdfplumber' or 'pypdf'. Install with: pip install pdfplumber"
        ) from exc

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
