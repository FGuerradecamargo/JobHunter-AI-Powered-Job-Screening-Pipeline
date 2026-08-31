from __future__ import annotations

from typing import Any

from services.ai.llm_client import LLMClient
from services.ai.prompt_builder import (
    build_career_memory_prompt,
)
from services.ai.response_parser import (
    parse_career_memory_response,
)


class CareerMemoryInterpreter:
    def __init__(
        self,
        llm_client: LLMClient,
    ) -> None:
        self.llm_client = llm_client

    def interpret(
        self,
        *,
        current_memory: dict[str, Any],
        recent_delta: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:
        if not isinstance(
            current_memory,
            dict,
        ):
            raise ValueError(
                "current_memory must "
                "be a dictionary."
            )

        if not isinstance(
            recent_delta,
            list,
        ):
            raise ValueError(
                "recent_delta must "
                "be a list."
            )

        allowed_evidence_refs = {
            str(
                item.get(
                    "evidence_ref",
                    "",
                )
            ).strip()
            for item in recent_delta
            if isinstance(
                item,
                dict,
            )
            and str(
                item.get(
                    "evidence_ref",
                    "",
                )
            ).strip()
        }

        prompt = (
            build_career_memory_prompt(
                current_memory=(
                    current_memory
                ),
                recent_delta=(
                    recent_delta
                ),
            )
        )

        raw_response = (
            self.llm_client.generate(
                prompt
            )
        )

        return parse_career_memory_response(
            response=raw_response,
            allowed_evidence_refs=(
                allowed_evidence_refs
            ),
        )
