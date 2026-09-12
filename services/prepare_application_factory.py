from services.application_context_service import ApplicationContextService
from services.application_contract_service import ApplicationContractService
from services.prepare_application_service import PrepareApplicationService
from services.tailored_cv_generation_service import TailoredCVGenerationService
from services.tailored_cv_generator_client import TailoredCVGeneratorClient


def build_prepare_application_service(
    *,
    generator_client: TailoredCVGeneratorClient,
) -> PrepareApplicationService:
    return PrepareApplicationService(
        contract_service=ApplicationContractService(),
        context_service=ApplicationContextService(),
        generation_service=TailoredCVGenerationService(generator_client),
    )
