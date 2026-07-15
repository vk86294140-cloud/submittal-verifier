import sys
import types

import pytest

from speccheck.parse_pdf import load_text, load_text_bytes


def test_load_text_bytes_txt_passthrough():
    assert load_text_bytes("spec.txt", b"hello world") == "hello world"


def test_load_text_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_text(tmp_path / "nope.txt")


def test_load_text_txt_file(tmp_path):
    p = tmp_path / "spec.txt"
    p.write_text("some spec text", encoding="utf-8")
    assert load_text(p) == "some spec text"


class _FakePage:
    def extract_text(self):
        return "page text"


class _FakePdf:
    def __init__(self):
        self.pages = [_FakePage(), _FakePage()]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakePdfplumber(types.ModuleType):
    def open(self, path):
        return _FakePdf()


def test_load_text_bytes_pdf_uses_pdfplumber(monkeypatch):
    fake = _FakePdfplumber("pdfplumber")
    monkeypatch.setitem(sys.modules, "pdfplumber", fake)
    out = load_text_bytes("submittal.pdf", b"%PDF-1.4 fake bytes")
    assert out == "page text\npage text"
