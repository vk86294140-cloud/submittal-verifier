"""Document loading.

Accepts ``.txt`` directly and ``.pdf`` when a PDF backend is installed.
Kept dependency-light: PDF support is optional so the tool and its tests run
without native libraries, while real-world PDFs still work when ``pdfplumber``
or ``pypdf`` is present.
"""

from __future__ import annotations

from pathlib import Path


def load_text(path: str | Path) -> str:
    """Return the plain text of a spec or submittal document."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".pdf":
        return _load_pdf(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_pdf(path: Path) -> str:
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        pdfplumber = None

    if pdfplumber is not None:
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "Reading PDF requires 'pdfplumber' or 'pypdf'. "
            "Install with: pip install pdfplumber"
        ) from exc

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
