from models.tailored_cv_contract import (
    TailoredCVGenerationRequest,
    TailoredCVRepairRequest,
)
from services.tailored_cv_generator_client import TailoredCVGeneratorClient


class TailoredCVGeneratorAdapter(TailoredCVGeneratorClient):
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def generate(
        self,
        request: TailoredCVGenerationRequest | TailoredCVRepairRequest,
    ) -> str:
        return self.llm_client.generate(request.prompt)
