"""Construct initial CPV2 state from confirmed sources; never persist it."""
from dataclasses import replace
import hashlib
import json
from typing import TYPE_CHECKING

from models.candidate_past import CandidateInput, CandidatePast, Certification, Education, Experience
from models.candidate_present import CandidatePresent
from models.candidate_future import CandidateFuture
from models.candidate_priorities import CandidatePriorities
from models.candidate_profile_snapshot import CandidateProfileSnapshot
from models.company_interview import V4_VERSION
from models.interpretation_boundary import StructuredInterpreter
from services import professional_facts_operation as facts_operation
from services import candidate_skills_operation as skills_operation
from services import candidate_priorities_operation as priorities_operation

if TYPE_CHECKING:
    from services.candidate_onboarding_repository import CandidateOnboardingRepository


class ProfileGenerationError(ValueError):
    """Safe stage-only failure; no partial Snapshot is returned."""

    def __init__(self, stage: str):
        self.stage = stage
        super().__init__(f"Candidate profile generation failed at {stage}.")


def _source_id(namespace: str, *identity: str) -> str:
    if any(type(value) is not str or not value.strip() for value in identity):
        raise ValueError("Source identity must be nonblank.")
    encoded = json.dumps([namespace, *identity], ensure_ascii=True, separators=(",", ":"))
    return namespace + ":" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ProfileGenerator:
    def __init__(self, *, onboarding_repository: "CandidateOnboardingRepository",
                 facts_interpreter: StructuredInterpreter,
                 skills_interpreter: StructuredInterpreter,
                 priorities_interpreter: StructuredInterpreter):
        self._sources = onboarding_repository
        self._facts_interpreter = facts_interpreter
        self._skills_interpreter = skills_interpreter
        self._priorities_interpreter = priorities_interpreter

    def generate(self, candidate_id: str) -> CandidateProfileSnapshot:
        stage = "source"
        try:
            if type(candidate_id) is not str or not candidate_id.strip():
                raise ValueError("Candidate identity is required.")
            about = self._sources.get_onboarding(candidate_id)
            experiences = self._sources.list_work_experiences(candidate_id)
            education = self._sources.list_education(candidate_id)
            certifications = self._sources.list_certifications(candidate_id)
            if about is None or any(item.candidate_id != candidate_id for item in
                                    (about, *experiences, *education, *certifications)):
                raise ValueError("Candidate source scope is invalid.")

            prepared = []
            for source in experiences:
                if any(answer.interview_version != V4_VERSION or answer.question_version != V4_VERSION
                       for answer in source.confirmed_interview_answers):
                    raise ValueError("V4 confirmed source answers are required.")
                inputs = tuple(
                    CandidateInput(
                        _source_id("candidate-input-v1", candidate_id, source.id, answer.question_id),
                        answer.confirmed_text,
                    )
                    for answer in source.confirmed_interview_answers
                    if not answer.skipped and isinstance(answer.confirmed_text, str)
                    and answer.confirmed_text.strip()
                )
                prepared.append(Experience(source.id, source.company, source.role,
                                           source.start_date, source.end_date, inputs=inputs))
            past = CandidatePast(
                experiences=tuple(prepared),
                education=tuple(Education(item.id, item.institution, item.qualification, item.field)
                                for item in education),
                certifications=tuple(Certification(item.id, item.name, item.issuer,
                                                   issued_at=str(item.year_obtained))
                                     for item in certifications),
            )
            present = CandidatePresent(
                country=about.country if about.country.strip() else None,
                city=about.city if about.city.strip() else None,
                languages=tuple(about.spoken_languages),
            )

            stage = "facts"
            interpreted = []
            for experience in past.experiences:
                facts = ()
                if experience.inputs:
                    request = facts_operation.build_request(facts_operation.ProfessionalFactsInput(experience.inputs))
                    response = self._facts_interpreter.interpret(request)
                    facts = facts_operation.validate_response(request, response).output_payload.facts
                interpreted.append(replace(experience, facts=facts))
            past = replace(past, experiences=tuple(interpreted))

            stage = "skills"
            all_facts = tuple(fact for entity in (*past.experiences, *past.education) for fact in entity.facts)
            if all_facts:
                request = skills_operation.build_request(skills_operation.CandidateSkillsInput(all_facts))
                response = self._skills_interpreter.interpret(request)
                skills = skills_operation.validate_response(request, response).output_payload.skills
                present = replace(present, skills=skills)

            stage = "priorities"
            priorities = CandidatePriorities()
            if about.priority_declaration.strip():
                declaration = priorities_operation.PriorityDeclaration(
                    _source_id("priority-declaration-v1", candidate_id, "priority_declaration"),
                    about.priority_declaration,
                )
                request = priorities_operation.build_request(
                    priorities_operation.CandidatePrioritiesInput((declaration,)))
                response = self._priorities_interpreter.interpret(request)
                priorities = priorities_operation.validate_response(request, response).output_payload

            stage = "construction"
            return CandidateProfileSnapshot(candidate_id, 1, past, present, CandidateFuture(), priorities)
        except Exception:
            raise ProfileGenerationError(stage) from None
