from services.application_context_service import ApplicationContextService
from services.application_contract_service import ApplicationContractService
from services.prepare_application_service import PrepareApplicationService
from services.tailored_cv_generation_service import TailoredCVGenerationService
from services.tailored_cv_generator_client import TailoredCVGeneratorClient
from services.preparation_generation_claim_repository import (
    PreparationGenerationClaimRepository,
)


def build_prepare_application_service(
    *,
    generator_client: TailoredCVGeneratorClient,
    claim_repository=None,
) -> PrepareApplicationService:
    return PrepareApplicationService(
        contract_service=ApplicationContractService(),
        context_service=ApplicationContextService(),
        generation_service=TailoredCVGenerationService(generator_client),
        claim_repository=claim_repository,
    )


def build_production_prepare_application_service() -> PrepareApplicationService:
    from services.ai.openai_client import OpenAIClient
    from services.ai.tailored_cv_generator_adapter import TailoredCVGeneratorAdapter

    return build_prepare_application_service(
        generator_client=TailoredCVGeneratorAdapter(OpenAIClient()),
        claim_repository=PreparationGenerationClaimRepository(),
    )
