from models.candidate_profile import CandidateProfile
from models.job import Job


def build_prompt(
    job: Job,
    candidate_profile: CandidateProfile,
) -> str:
    return f"""
You are evaluating whether a job opportunity is suitable for a candidate.

Your task is to compare the candidate profile with the job description and produce a structured recommendation.

Candidate profile:
{candidate_profile}

Job:
Title: {job.title}
Company: {job.company}
Location: {job.location}
Description:
{job.description}

Evaluate the following:

1. Current fit
How well the candidate matches the role today.

2. Growth value
How useful this role would be for the candidate's professional direction.

3. Strengths
Which candidate characteristics align with the role.

4. Gaps
Which important requirements are missing or weak.

5. Recommendation
Choose exactly one:
- apply
- consider
- stretch
- ignore

Return only valid JSON using exactly this structure:

{{
  "recommendation": "apply",
  "current_fit": 0,
  "growth_value": 0,
  "strengths": [],
  "gaps": [],
  "reason": ""
}}

Rules:
- current_fit must be an integer from 0 to 100.
- growth_value must be an integer from 0 to 100.
- strengths must be a list of short strings.
- gaps must be a list of short strings.
- reason must be concise and specific.
- Do not include markdown.
- Do not include explanations outside the JSON.
""".strip()