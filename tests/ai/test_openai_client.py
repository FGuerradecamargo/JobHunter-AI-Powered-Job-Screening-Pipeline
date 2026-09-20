import services.ai.openai_client as openai_client_module
from services.ai.openai_client import OpenAIClient


def test_openai_client_has_bounded_transport_policy(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        openai_client_module,
        "OpenAI",
        FakeOpenAI,
    )

    OpenAIClient(model="test-model")

    assert captured["api_key"] == "test-key"
    assert captured["timeout"] == 120.0
    assert captured["max_retries"] == 0
