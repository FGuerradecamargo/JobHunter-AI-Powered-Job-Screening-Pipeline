import json

import pytest

from services.career_memory_interpreter import (
    CareerMemoryInterpreter,
)
from services.ai.response_parser import (
    parse_career_memory_response,
)


class FakeLLM:
    def __init__(
        self,
        response,
    ):
        self.response = response
        self.calls = 0
        self.prompts = []

    def generate(
        self,
        prompt,
    ):
        self.calls += 1
        self.prompts.append(
            prompt
        )
        return self.response


def _delta():
    return [
        {
            "evidence_ref": (
                "fact:"
                "career_updates:"
                "collection"
            ),
            "authority": "fact",
            "source_type": (
                "career_updates"
            ),
            "source_ref": (
                "collection"
            ),
            "state": [
                {
                    "description": (
                        "Started SQL training"
                    )
                }
            ],
        },
        {
            "evidence_ref": (
                "market_evidence:"
                "market_position:"
                "historical"
            ),
            "authority": (
                "market_evidence"
            ),
            "source_type": (
                "market_position"
            ),
            "source_ref": (
                "historical"
            ),
            "state": {
                "sample_size": 20,
                "average_fit": 61.0,
            },
        },
    ]


def test_interpreter_uses_one_llm_call():
    response = json.dumps(
        {
            "inferences": [
                {
                    "statement": (
                        "Technical roles may "
                        "be becoming more viable."
                    ),
                    "confidence": 70,
                    "evidence_refs": [
                        (
                            "market_evidence:"
                            "market_position:"
                            "historical"
                        )
                    ],
                }
            ],
            "hypotheses": [],
            "continuity_note": (
                "Watch whether technical "
                "role fit continues improving."
            ),
        }
    )

    llm = FakeLLM(
        response
    )

    interpreter = (
        CareerMemoryInterpreter(
            llm
        )
    )

    result = interpreter.interpret(
        current_memory={
            "facts": {},
        },
        recent_delta=_delta(),
    )

    assert llm.calls == 1

    assert len(
        result["inferences"]
    ) == 1

    assert (
        result["inferences"][0][
            "confidence"
        ]
        == 70
    )


def test_unknown_evidence_ref_is_rejected():
    response = json.dumps(
        {
            "inferences": [
                {
                    "statement": (
                        "Invented conclusion"
                    ),
                    "confidence": 90,
                    "evidence_refs": [
                        "fact:invented:source"
                    ],
                }
            ],
            "hypotheses": [],
            "continuity_note": "",
        }
    )

    llm = FakeLLM(
        response
    )

    interpreter = (
        CareerMemoryInterpreter(
            llm
        )
    )

    with pytest.raises(
        ValueError
    ):
        interpreter.interpret(
            current_memory={},
            recent_delta=_delta(),
        )


def test_extra_top_level_field_is_rejected():
    response = json.dumps(
        {
            "inferences": [],
            "hypotheses": [],
            "continuity_note": "",
            "facts": {
                "invented": True,
            },
        }
    )

    with pytest.raises(
        ValueError
    ):
        parse_career_memory_response(
            response=response,
            allowed_evidence_refs=set(),
        )


def test_inference_cannot_contain_extra_fields():
    response = json.dumps(
        {
            "inferences": [
                {
                    "statement": "Possible pattern",
                    "confidence": 60,
                    "evidence_refs": [],
                    "authority": "fact",
                }
            ],
            "hypotheses": [],
            "continuity_note": "",
        }
    )

    with pytest.raises(
        ValueError
    ):
        parse_career_memory_response(
            response=response,
            allowed_evidence_refs=set(),
        )


def test_invalid_confidence_is_rejected():
    response = json.dumps(
        {
            "inferences": [],
            "hypotheses": [
                {
                    "statement": (
                        "Possible preference"
                    ),
                    "confidence": 101,
                    "evidence_refs": [],
                }
            ],
            "continuity_note": "",
        }
    )

    with pytest.raises(
        ValueError
    ):
        parse_career_memory_response(
            response=response,
            allowed_evidence_refs=set(),
        )


def test_valid_empty_interpretation_is_allowed():
    response = json.dumps(
        {
            "inferences": [],
            "hypotheses": [],
            "continuity_note": "",
        }
    )

    result = (
        parse_career_memory_response(
            response=response,
            allowed_evidence_refs=set(),
        )
    )

    assert result == {
        "inferences": [],
        "hypotheses": [],
        "continuity_note": "",
    }


def test_duplicate_statement_is_rejected():
    response = json.dumps(
        {
            "inferences": [
                {
                    "statement": (
                        "Possible pattern"
                    ),
                    "confidence": 60,
                    "evidence_refs": [],
                },
                {
                    "statement": (
                        "possible pattern"
                    ),
                    "confidence": 70,
                    "evidence_refs": [],
                },
            ],
            "hypotheses": [],
            "continuity_note": "",
        }
    )

    with pytest.raises(
        ValueError
    ):
        parse_career_memory_response(
            response=response,
            allowed_evidence_refs=set(),
        )
