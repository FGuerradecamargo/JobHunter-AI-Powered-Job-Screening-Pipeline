import json
from dataclasses import asdict

from models.candidate_onboarding import CandidateOnboarding
from models.work_experience import WorkExperience


def build_candidate_profile_prompt(
    onboarding: CandidateOnboarding,
    experiences: list[WorkExperience],
) -> str:
    onboarding_json = json.dumps(
        asdict(onboarding),
        ensure_ascii=False,
        indent=2,
    )

    experiences_json = json.dumps(
        [
            asdict(experience)
            for experience in experiences
        ],
        ensure_ascii=False,
        indent=2,
    )

    return f"""
You are a professional profile analyst.

Your task is to understand the candidate's real professional identity
from their own narrative.

Do not rewrite their answers as a CV.

Instead, infer the professional profile behind the experience:
- what kind of work they actually know how to do;
- what problems they have experience solving;
- what skills are evidenced by their daily work;
- what strengths repeatedly appear;
- what professional level is supported by the evidence;
- what kinds of roles naturally connect with their experience;
- what areas they could reasonably develop next.

The candidate may describe skills indirectly.

For example:

"I worked through a queue of cases and decided which ones needed escalation"
may support:
- case management
- prioritisation
- investigation
- escalation handling

"I reviewed transactions and account history to understand what happened"
may support:
- investigation
- data analysis
- root cause analysis

"I created Jira tickets and worked with Engineering"
may support:
- technical documentation
- escalation management
- cross-functional collaboration

However, never invent experience.

A skill can only be included when there is reasonable evidence in the
candidate's answers.

Do not convert familiarity into professional expertise.

Do not claim advanced technical experience when the narrative only
supports basic or working knowledge.

When the evidence is weak or ambiguous, prefer conservative wording.

The candidate's career story describes how their career evolved.

The day-to-day narrative is especially important because it reveals what
the candidate actually did repeatedly in practice.

Candidate onboarding:

{onboarding_json}

Professional experiences:

{experiences_json}

Return only valid JSON using exactly this structure:

{{
    "current_role": "",
    "current_level": "",
    "professional_summary": "",
    "target_roles": [],
    "skills": [],
    "strengths": [],
    "development_areas": []
}}

Rules:

- current_role should describe the candidate's current professional
  positioning, not simply copy the latest job title when that would be
  misleading.

- current_level should use a concise professional level such as:
  junior, mid-level, senior, specialist, team lead, manager, or another
  clearly justified level.

- professional_summary should be concise and factual.

- target_roles should contain realistic roles that connect the
  candidate's current experience with their stated professional
  direction.

- skills should contain capabilities supported by actual evidence.

- strengths should describe recurring professional strengths, not vague
  personality compliments.

- development_areas should identify skills or experience that would
  reasonably help the candidate move toward their desired direction.
- spoken_languages should preserve languages supplied by the candidate.

- Do not invent companies, tools, technologies, achievements, metrics,
  responsibilities or years of experience.

- Do not include markdown.

- Do not include any text outside the JSON.

- current_role must be a short professional positioning label,
  normally 2 to 6 words.

- Do not write a sentence or summary in current_role.

- skills must be consolidated professional capabilities.

- Do not create a separate skill for every task mentioned.

- Prefer broader evidence-based capabilities such as:
  "Fraud investigations"
  "Escalation handling"
  "Root cause analysis"
  "Python automation"
  "Process improvement"
  "Operational reporting"

- Avoid including incidental or older task-specific abilities unless
  they are relevant to the candidate's current professional direction.
""".strip()
