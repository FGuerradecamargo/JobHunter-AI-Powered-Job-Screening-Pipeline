from typing import Protocol

from models.tailored_cv_contract import (
    TailoredCVGenerationRequest,
    TailoredCVRepairRequest,
)


class TailoredCVGeneratorClient(Protocol):
    def generate(
        self,
        request: TailoredCVGenerationRequest | TailoredCVRepairRequest,
    ) -> dict | str:
        ...
