import json

from models.job import Job


def build_job_profile_prompt(job: Job) -> str:
    return f"""
You are analyzing a job vacancy.

Your task is ONLY to determine what kind of professional the company
is trying to hire.

Do NOT evaluate any candidate.
Do NOT recommend whether anyone should apply.
Do NOT infer requirements that are not supported by the vacancy.

JOB

Title: {job.title}
Company: {job.company}
Location: {job.location}
Remote: {job.remote}
Salary: {job.salary}

Description:

{job.description or job.raw_text}

Determine:

1. canonical_role
   The clearest standard name for the actual role.

2. role_family
   The professional family this role belongs to.

3. seniority
   Use one of:
   entry
   junior
   mid
   senior
   lead
   manager
   director
   executive
   unclear

4. core_mission
   What this person is fundamentally hired to accomplish.

5. must_have_capabilities
   Capabilities central to doing the job from day one.

6. must_have_experience
   Professional experience that appears genuinely necessary.

7. nice_to_have
   Useful but non-essential skills, tools or experience.

8. domain
   Relevant industry or professional domain.

9. expected_autonomy
   Use:
   low
   medium
   high
   unclear

10. structural_requirements
    Requirements that may block a candidate regardless of transferable skills.
    Examples:
    mandatory certification,
    work authorisation,
    required language,
    mandatory location,
    driving licence,
    required degree when genuinely mandatory.

11. work_conditions
    Important conditions such as shifts, on-call, travel, relocation,
    contract type or unusual schedule.

12. summary
    Maximum 3 short sentences explaining what kind of professional
    the company is actually seeking.

Separate mandatory requirements from preferences carefully.

Return ONLY valid JSON:

{{
  "canonical_role": "",
  "role_family": "",
  "seniority": "unclear",
  "core_mission": "",
  "must_have_capabilities": [],
  "must_have_experience": [],
  "nice_to_have": [],
  "domain": "",
  "expected_autonomy": "unclear",
  "structural_requirements": [],
  "work_conditions": [],
  "summary": ""
}}
""".strip()
