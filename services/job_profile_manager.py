"""Runtime facade over the official, provenance-bound JobProfile snapshots."""
from models.job_profile import JobProfile
from models.profile_interpretation import AI_JOB_PROFILE_SCHEMA_VERSION, JobRequirementStatus
from services.profile_interpretation_service import ProfileInterpretationService
from services.profile_snapshot_repository import ProfileSnapshotRepository
from services.job_source_repository import JobSourceRepository


JOB_PROFILE_VERSION = AI_JOB_PROFILE_SCHEMA_VERSION


class JobProfileManager:
    def __init__(self, service, *, source_repository=None, snapshot_repository=None):
        self.sources = source_repository or JobSourceRepository()
        self.snapshots = snapshot_repository or ProfileSnapshotRepository()
        self.interpretation = ProfileInterpretationService(self.snapshots, service)

    def get_official(self, job_id, *, candidate_id=None):
        facts = self.sources.load_job_hard_facts(job_id, candidate_id=candidate_id)
        return self.interpretation.job_profile(hard_facts=facts)

    def get(self, job_id, *, candidate_id=None):
        facts = self.sources.load_job_hard_facts(job_id, candidate_id=candidate_id)
        snapshot = self.snapshots.job_for_signature(job_id, facts.job_signature, JOB_PROFILE_VERSION)
        return self._compatibility_view(snapshot) if snapshot else None

    def get_or_create(self, job, *, candidate_id=None):
        return self._compatibility_view(self.get_official(job.id, candidate_id=candidate_id))

    @staticmethod
    def _compatibility_view(snapshot):
        # Transitional read projection only. No independent cache, extraction or
        # inference; remaining consumers are replaced by the HiringCase cutover.
        return JobProfile(
            job_id=snapshot.job_id,
            core_mission=snapshot.problem_to_solve,
            must_have_capabilities=[need.label for need in snapshot.needs
                                    if need.requirement_status is JobRequirementStatus.REQUIRED],
            nice_to_have=[need.label for need in snapshot.needs
                          if need.requirement_status in {JobRequirementStatus.PREFERRED, JobRequirementStatus.USEFUL}],
            key_responsibilities=list(snapshot.responsibilities),
            tools_and_technologies=list(snapshot.tools_as_means),
            role_context=snapshot.context,
            summary=snapshot.problem_to_solve,
        )
