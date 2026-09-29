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


def test_openai_client_uses_responses_structured_output(
    monkeypatch,
):
    from types import SimpleNamespace

    from pydantic import BaseModel

    captured = {}

    class Output(BaseModel):
        value: str

    class Parsed:
        def model_dump(
            self,
            *,
            mode,
        ):
            assert mode == "json"
            return {
                "value": "structured"
            }

    class Responses:
        def parse(
            self,
            **kwargs,
        ):
            captured.update(
                kwargs
            )

            return SimpleNamespace(
                output_parsed=Parsed()
            )

    class FakeOpenAI:
        def __init__(
            self,
            **kwargs,
        ):
            self.responses = Responses()

    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )

    monkeypatch.setattr(
        openai_client_module,
        "OpenAI",
        FakeOpenAI,
    )

    client = OpenAIClient(
        model="test-model"
    )

    result = client.generate_structured(
        "profile prompt",
        Output,
    )

    assert result == {
        "value": "structured"
    }

    assert captured == {
        "model": "test-model",
        "input": "profile prompt",
        "text_format": Output,
    }
