"""Provider transport schema/hooks for the candidate skills operation."""
from dataclasses import asdict
import json

from pydantic import BaseModel, ConfigDict, Field

from models.candidate_present import CandidateSkill, ProfessionalFactRef
from models.professional_ontology import Skill, SkillLevel
from services.candidate_skills_operation import (
    INSTRUCTIONS, OPERATION, CandidateSkillsInput, CandidateSkillsOutput,
    build_request, normalized_skill_id, validate_response,
)
from services.interpretation_operation_spec import InterpretationOperationSpec


class _SkillOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    category: str
    subcategory: str | None
    level: SkillLevel = Field(strict=False)
    evidence_refs: list[str]


class CandidateSkillsStructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    skills: list[_SkillOutput]


def _validate_request(request) -> None:
    if request != build_request(request.input_payload):
        raise ValueError("Invalid CandidateSkills request identity.")


def _serialize_input(payload: CandidateSkillsInput) -> str:
    return json.dumps(asdict(payload), sort_keys=True, ensure_ascii=True)


def _parse_output(raw: dict) -> CandidateSkillsOutput:
    result = CandidateSkillsStructuredOutput.model_validate(raw)
    return CandidateSkillsOutput(tuple(
        CandidateSkill(
            Skill(normalized_skill_id(item.name), item.name, item.category, item.subcategory),
            item.level, tuple(ProfessionalFactRef(ref) for ref in item.evidence_refs),
        ) for item in result.skills
    ))


CANDIDATE_SKILLS_SPEC = InterpretationOperationSpec[CandidateSkillsInput, CandidateSkillsOutput](
    operation=OPERATION, instructions=INSTRUCTIONS, response_model=CandidateSkillsStructuredOutput,
    validate_request=_validate_request, serialize_input=_serialize_input,
    parse_output=_parse_output, validate_response=validate_response,
)
