from types import SimpleNamespace

import anthropic

from src import llm_provider


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
        def __init__(self, api_key):
            assert api_key == "secret"
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
