from typing import Protocol, runtime_checkable

from models.tailored_cv_contract import (
    TailoredCVGenerationRequest,
    TailoredCVRepairRequest,
)


@runtime_checkable
class TailoredCVGeneratorClient(Protocol):
    def generate(
        self,
        request: TailoredCVGenerationRequest | TailoredCVRepairRequest,
    ) -> dict | str:
        ...
