import sys
import types

from speccheck.llm import _parse, enrich
from speccheck.models import RequirementKind


def test_enrich_without_api_key_returns_empty(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert enrich("some spec text") == []


def test_parse_valid_json_array():
    payload = '[{"kind": "standard", "keyword": "ASTM E84", "text": "Comply with ASTM E84."}]'
    reqs = _parse(payload)
    assert len(reqs) == 1
    assert reqs[0].kind is RequirementKind.STANDARD
    assert reqs[0].keyword == "astm e84"


def test_parse_unknown_kind_falls_back_to_general():
    payload = '[{"kind": "bogus", "text": "some clause"}]'
    reqs = _parse(payload)
    assert reqs[0].kind is RequirementKind.GENERAL


def test_parse_malformed_json_returns_empty():
    assert _parse("not json at all") == []
    assert _parse("no brackets here") == []


class _TextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeMessages:
    def create(self, **kwargs):
        payload = '[{"kind": "general", "text": "color to match architect sample"}]'
        return types.SimpleNamespace(content=[_TextBlock(payload)])


class _FakeAnthropic:
    def __init__(self, **kwargs):
        self.messages = _FakeMessages()


def test_enrich_with_fake_anthropic_client(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake = types.ModuleType("anthropic")
    fake.Anthropic = _FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake)

    reqs = enrich("some spec text")
    assert len(reqs) == 1
    assert reqs[0].text == "color to match architect sample"


def test_enrich_swallows_client_errors(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class _BoomMessages:
        def create(self, **kwargs):
            raise RuntimeError("api down")

    class _BoomAnthropic:
        def __init__(self, **kwargs):
            self.messages = _BoomMessages()

    fake = types.ModuleType("anthropic")
    fake.Anthropic = _BoomAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake)

    assert enrich("some spec text") == []
