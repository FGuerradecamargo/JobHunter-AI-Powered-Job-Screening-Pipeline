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

8. key_responsibilities
   The main activities the person will actually perform.
   Preserve concrete responsibilities from the vacancy.
   Maximum 8 concise items.

9. tools_and_technologies
   Named tools, systems, platforms, technologies or methodologies
   that materially matter to the role.
   Do not invent tools from the role family.
   Maximum 12 concise items.

10. required_qualifications
    Qualifications explicitly required or strongly expected,
    including relevant education, certifications or formal knowledge.
    Do not repeat items already captured as structural requirements
    unless the distinction is useful.
    Maximum 8 concise items.

11. stakeholders_and_collaboration
    Important teams, customers, partners or stakeholders this person
    is expected to work with.
    Only include relationships supported by the vacancy.
    Maximum 6 concise items.

12. domain
    Relevant industry or professional domain.

13. expected_autonomy
    Use:
    low
    medium
    high
    unclear

14. structural_requirements
    Requirements that may block a candidate regardless of transferable skills.
    Examples:
    mandatory certification,
    work authorisation,
    required language,
    mandatory location,
    driving licence,
    required degree when genuinely mandatory.

15. work_conditions
    Important conditions such as shifts, on-call, travel, relocation,
    contract type or unusual schedule.

16. important_details
    Material facts from the vacancy that are useful for evaluating,
    tailoring an application or preparing for an interview but do not
    fit naturally into the fields above.

    Examples:
    unusual ownership expectations,
    scale or complexity,
    specific customer segment,
    regulatory context,
    unusual operational responsibility.

    Do not use this field as a copy of the description.
    Maximum 8 concise items.

17. role_context
    One short paragraph describing the practical environment of the role:
    what kind of work setting this is, what the role sits around, and
    any context needed to understand the responsibilities.

    Do not invent company structure or team details.

18. summary
    Maximum 3 short sentences explaining what kind of professional
    the company is actually seeking.

Separate mandatory requirements from preferences carefully.

Preserve materially useful vacancy information, but compress repetition
and marketing language.

The resulting JobProfile must contain enough factual information to support
later candidate fit analysis, CV tailoring and interview preparation without
requiring the full vacancy description again.

Return ONLY valid JSON:

{{
  "canonical_role": "",
  "role_family": "",
  "seniority": "unclear",
  "core_mission": "",
  "must_have_capabilities": [],
  "must_have_experience": [],
  "nice_to_have": [],
  "key_responsibilities": [],
  "tools_and_technologies": [],
  "required_qualifications": [],
  "stakeholders_and_collaboration": [],
  "domain": "",
  "expected_autonomy": "unclear",
  "structural_requirements": [],
  "work_conditions": [],
  "important_details": [],
  "role_context": "",
  "summary": ""
}}
""".strip()
