import sys
from types import SimpleNamespace

import anthropic

from src import llm_provider


def test_gemini_uses_google_genai_current_client_and_schema(monkeypatch):
    captured = {}

    class HttpOptions:
        def __init__(self, **kwargs):
            captured["http_options"] = kwargs

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            captured["generation"] = kwargs

    fake_types = SimpleNamespace(
        HttpOptions=HttpOptions,
        GenerateContentConfig=GenerateContentConfig,
    )

    class Models:
        def generate_content(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(text=' {"ok": true} ')

    class Client:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.models = Models()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    fake_genai = SimpleNamespace(Client=Client, types=fake_types)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    import google
    monkeypatch.setattr(google, "genai", fake_genai, raising=False)
    monkeypatch.setattr(
        llm_provider,
        "env",
        lambda key, default="": "gemini-secret" if key == "GEMINI_API_KEY" else default,
    )
    monkeypatch.setattr(
        llm_provider,
        "_llm_cfg",
        lambda: {
            "gemini_model": "gemini-3.6-flash",
            "max_tokens": 4096,
            "request_timeout_sec": 600,
        },
    )
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }

    assert llm_provider._via_gemini("prompt", "system", schema) == '{"ok": true}'
    assert captured["http_options"] == {"timeout": 600000}
    assert captured["client"]["api_key"] == "gemini-secret"
    assert captured["request"]["model"] == "gemini-3.6-flash"
    assert captured["generation"] == {
        "system_instruction": "system",
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
        "response_json_schema": schema,
    }


def test_anthropic_uses_structured_output_and_larger_policy_budget(monkeypatch):
    captured = {}

    class Messages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(text='{"ok":true}')],
            )

    class Client:
        def __init__(self, api_key, **kwargs):
            assert api_key == "secret"
            assert kwargs == {"timeout": 600, "max_retries": 1}
            self.messages = Messages()

    monkeypatch.setattr(anthropic, "Anthropic", Client)
    monkeypatch.setattr(llm_provider, "env", lambda key, default="": "secret" if key == "ANTHROPIC_API_KEY" else default)
    monkeypatch.setattr(
        llm_provider, "_llm_cfg",
        lambda: {"anthropic_model": "claude-sonnet-4-6", "max_tokens": 4096},
    )
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }

    assert llm_provider._via_anthropic("prompt", "system", schema) == '{"ok":true}'
    assert captured["max_tokens"] == 8192
    assert captured["output_config"] == {
        "format": {"type": "json_schema", "schema": schema},
    }
