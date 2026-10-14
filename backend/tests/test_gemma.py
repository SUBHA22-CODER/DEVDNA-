import pytest

from app.ai import gemma as gemma_mod
from app.ai.gemma import AIError, GemmaService, extract_json, response_text
from app.config import settings


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": {"b": 2}} done') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        extract_json("no json here")


class _Part:
    def __init__(self, text, thought=False):
        self.text, self.thought = text, thought


class _Resp:
    def __init__(self, parts):
        self.candidates = [type("C", (), {"content": type("X", (), {"parts": parts})()})()]
        self.text = None


def test_response_text_skips_thoughts():
    assert response_text(_Resp([_Part("thinking...", True), _Part('{"x":1}')])) == '{"x":1}'


def test_not_configured_raises():
    svc = GemmaService()
    with pytest.raises(AIError) as exc:
        svc._get_client()
    assert exc.value.code == "not_configured"


def test_invalid_output_retries_then_fails(monkeypatch):
    svc = GemmaService()
    calls = []
    monkeypatch.setattr(svc, "_call", lambda prompt: calls.append(prompt) or "not json at all")
    with pytest.raises(AIError) as exc:
        svc.generate("chat", "question", {"E1"})
    assert exc.value.code == "invalid_output" and len(calls) == 2


def test_valid_output_is_validated_and_ungrounded_refs_removed(monkeypatch):
    svc = GemmaService()
    monkeypatch.setattr(svc, "_call", lambda p: '{"answer": "Uses sqlite [E1]", "evidence_used": ["E1", "E99"], "confidence": "high"}')
    parsed, meta = svc.generate("chat", "q", {"E1", "E2"})
    assert parsed.evidence_used == ["E1"]
    assert meta["ungrounded_refs"] == ["E99"]
    assert meta["model"] == settings.gemma_model


def test_schema_violation_is_rejected(monkeypatch):
    svc = GemmaService()
    monkeypatch.setattr(svc, "_call", lambda p: '{"answer": "x", "confidence": "certain"}')
    with pytest.raises(AIError, match="did not match"):
        svc.generate("chat", "q", set())


def test_error_mapping(monkeypatch):
    from google.genai import errors

    svc = GemmaService()
    monkeypatch.setattr(settings, "gemma_model", "gemma-4-26b-a4b-it")
    assert svc._map_error(errors.ClientError(429, {"error": {"message": "quota"}})).code == "rate_limited"
    assert svc._map_error(errors.ClientError(404, {"error": {"message": "nf"}})).code == "model_unavailable"
    assert svc._map_error(errors.ClientError(403, {"error": {"message": "denied"}})).code == "unauthorized"
    assert svc._map_error(errors.ServerError(504, {"error": {"message": "deadline"}})).code == "timeout"
    assert svc._map_error(errors.ServerError(503, {"error": {"message": "down"}})).code == "provider_error"
    assert svc._map_error(TimeoutError("read timeout")).code == "timeout"


def test_api_key_never_in_error_messages(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaFAKEKEYFORTESTS000000000000000000000")
    svc = GemmaService()
    err = svc._map_error(RuntimeError("bad request with key AIzaFAKEKEYFORTESTS000000000000000000000"))
    assert "AIzaFAKE" not in err.message


def test_model_is_never_switched(monkeypatch):
    """The configured model id is passed to the SDK unchanged."""
    seen = {}

    class FakeModels:
        def generate_content_stream(self, model, contents, config):
            seen["model"] = model
            yield _Resp([_Part("reasoning", True)])
            yield _Resp([_Part('{"answer": ')])
            yield _Resp([_Part('"ok"}')])

    svc = GemmaService()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    svc._client = type("Client", (), {"models": FakeModels()})()
    parsed, meta = svc.generate("chat", "q", set())
    assert seen["model"] == settings.gemma_model == meta["model"]
    assert parsed.answer == "ok"  # streamed chunks joined, thought parts excluded
    assert gemma_mod.SYSTEM_INSTRUCTION.startswith("You are DevDNA")


def test_transient_5xx_retries_and_succeeds(monkeypatch):
    """A transient 500/503 error is automatically retried and succeeds."""
    from google.genai import errors

    attempts = {"count": 0}

    class FlakyModels:
        def generate_content_stream(self, model, contents, config):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise errors.ServerError(503, {"error": {"message": "Service unavailable"}})
            yield _Resp([_Part('{"answer": "recovered"}')])

    svc = GemmaService()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("time.sleep", lambda s: None)
    svc._client = type("Client", (), {"models": FlakyModels()})()
    parsed, meta = svc.generate("chat", "q", set())
    assert attempts["count"] == 2
    assert parsed.answer == "recovered"

