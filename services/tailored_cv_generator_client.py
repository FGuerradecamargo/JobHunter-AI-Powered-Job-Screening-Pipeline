from typing import Protocol

from models.tailored_cv_contract import TailoredCVGenerationRequest


class TailoredCVGeneratorClient(Protocol):
    def generate(self, request: TailoredCVGenerationRequest) -> dict | str:
        ...
