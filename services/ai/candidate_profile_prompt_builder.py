import json
from dataclasses import asdict

from models.candidate_onboarding import CandidateOnboarding
from models.work_experience import WorkExperience
from models.career_update import CareerUpdate


def build_candidate_profile_prompt(
    onboarding: CandidateOnboarding,
    experiences: list[WorkExperience],
    career_updates: list[CareerUpdate] | None = None,
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


    career_updates_json = json.dumps(
        [
            asdict(update)
            for update in (
                career_updates or []
            )
        ],
        ensure_ascii=False,
        indent=2,
    )

    return f"""
You are a professional profile analyst.

Your task is to build a structured professional model of the candidate
from their own narrative and work history.

This is NOT a CV-writing task.

The profile will later be used to compare the candidate fairly against
job opportunities, so preserve professional evidence instead of
compressing the person's history into a few generic skills.

You must distinguish between:

1. PROVEN CAPABILITIES
Capabilities supported by repeated or meaningful professional evidence.

2. TRANSFERABLE CAPABILITIES
Capabilities demonstrated in one context that could reasonably transfer
to another professional context.

3. DEVELOPING CAPABILITIES
Knowledge, skills or areas the candidate is actively developing or has
limited exposure to, but which are not yet strongly proven professionally.

4. PROFESSIONAL STRENGTHS
Recurring patterns in how the candidate works, such as investigation,
ownership, prioritisation, structured problem solving, training,
process improvement or cross-functional coordination.

5. TOOLS
Specific software, technologies, systems or technical tools explicitly
supported by the candidate's narrative.

6. DOMAIN EXPERIENCE
Professional environments in which the candidate has actual experience,
such as fraud operations, payments, hospitality, manufacturing,
customer operations, architecture, logistics or software support.

7. CAREER DIRECTION
Where the candidate explicitly says they want to go professionally.

Past experience must NOT automatically determine future direction.

For example, a waiter studying IT and explicitly seeking an IT career
should have hospitality represented as proven experience while IT-related
roles may appear as bridge or target directions when supported by their
education, development and stated goals.

Never invent experience.

A capability can only be marked as proven when there is reasonable
evidence in the candidate's answers.

Do not convert familiarity into professional expertise.

Do not claim advanced technical experience when the narrative only
supports basic or working knowledge.

When evidence is weak or ambiguous, use conservative wording.

The candidate's day-to-day narrative is especially important because
it shows what they repeatedly did in practice.

For each professional experience, preserve the evidence separately.
Do not merge all jobs into one generic summary.

Candidate onboarding:

{onboarding_json}

Professional experiences:

{experiences_json}

Career updates since the original professional history was provided:

{career_updates_json}

Career updates are later events in the candidate's professional life.

They may describe:
- a promotion;
- a new job;
- leaving or losing a job;
- a completed course or certification;
- a newly developed skill;
- new responsibilities;
- a relevant project;
- a change in professional direction;
- another meaningful professional change.

Treat career updates as additional source evidence.

When a career update changes or supersedes older information, use the
newer information when determining the candidate's CURRENT state.

Do not erase older professional history merely because a newer event
exists.

A completed course may support developing knowledge, but must not
automatically be treated as professional experience.

A new responsibility may strengthen demonstrated capabilities when
the update provides reasonable evidence.

Return only valid JSON using exactly this structure:

{{
    "current_role": "",
    "current_level": "",
    "professional_summary": "",

    "target_roles": [],
    "skills": [],
    "strengths": [],
    "development_areas": [],

    "professional_experiences": [
        {{
            "source_experience_id": "",
            "company": "",
            "stated_role": "",
            "inferred_role": "",
            "role_family": "",
            "summary": "",
            "responsibilities": [],
            "demonstrated_capabilities": [],
            "transferable_capabilities": [],
            "tools": [],
            "domains": [],
            "evidence": []
        }}
    ],

    "proven_capabilities": [],
    "transferable_capabilities": [],
    "developing_capabilities": [],
    "technical_tools": [],
    "domain_experience": [],

    "competitive_role_families": [],
    "bridge_role_families": [],
    "target_role_families": []
}}

GENERAL RULES

- Do not include markdown.
- Do not include text outside the JSON.
- Do not invent companies, job titles, tools, technologies,
  achievements, metrics, responsibilities or years of experience.
- Do not infer a formal job title unless the candidate supplied enough
  evidence to support it.
- If the formal title is not clear, stated_role may be empty.
- source_experience_id must exactly preserve the id supplied for that
  work experience.
- company must exactly preserve the company supplied in the experience.

CURRENT POSITIONING

- current_role should describe the candidate's current professional
  positioning, not blindly copy the latest formal job title.
- current_role must be a short professional positioning label,
  normally 2 to 6 words.
- current_level should use a concise professional level such as junior,
  mid-level, senior, specialist, team lead or manager, only when
  supported by the evidence.
- professional_summary should be concise, factual and evidence-based.

LEGACY COMPATIBILITY FIELDS

The following fields remain because other parts of the application
currently use them:

- target_roles
- skills
- strengths
- development_areas

Populate them consistently with the richer profile.

- target_roles should contain realistic individual role titles that
  connect the candidate's experience with their stated direction.
- skills should contain consolidated evidence-based professional
  capabilities.
- strengths should contain recurring professional strengths.
- development_areas should contain realistic areas that would help the
  candidate progress toward their desired direction.

PROFESSIONAL EXPERIENCE ANALYSIS

For every supplied WorkExperience, return one matching object in
professional_experiences.

- stated_role:
  Use the candidate's stated/formal role only when it appears in the
  source material. Do not invent one.

- inferred_role:
  Describe what the work functionally represents based on the actual
  responsibilities. This may differ from the formal title.

- role_family:
  Use a broad functional family such as:
  "Customer Operations",
  "Technical Support",
  "Fraud & Risk Operations",
  "Warehouse Operations",
  "Food & Beverage Service",
  "Architecture",
  "Manufacturing Operations".
  These examples are illustrative, not an exhaustive list.

- summary:
  Briefly explain what the candidate actually did in this experience.

- responsibilities:
  Include important recurring responsibilities evidenced by the
  narrative.

- demonstrated_capabilities:
  Include capabilities directly evidenced by this work.

- transferable_capabilities:
  Include capabilities from this experience that reasonably transfer
  to other professional contexts.

- tools:
  Include only tools or technologies explicitly supported by the source.

- domains:
  Include professional domains actually evidenced by this experience.

- evidence:
  Write short factual evidence statements derived from the source
  narrative.
  Evidence should explain WHY a capability was inferred.

Example:

Candidate says:
"I reviewed orders and account history, decided whether they were
fraudulent, escalated uncertain cases and created Jira tickets when
technical investigation was required."

Possible evidence:
- "Reviewed order and account history to make fraud decisions."
- "Escalated uncertain cases for further review."
- "Created Jira tickets for technical investigation."

Do not quote large portions of the candidate's narrative.

CAPABILITY CLASSIFICATION

proven_capabilities:
- capabilities strongly supported by professional experience.

transferable_capabilities:
- demonstrated capabilities that could reasonably apply to adjacent
  roles or industries.

developing_capabilities:
- skills or knowledge that are being developed or only lightly
  evidenced.

technical_tools:
- deduplicated tools and technologies supported by evidence.

domain_experience:
- deduplicated professional domains in which the candidate has actual
  experience.

ROLE FAMILIES

competitive_role_families:
- families where the candidate already has enough relevant professional
  evidence to compete realistically now.

bridge_role_families:
- adjacent families where the candidate has a credible transferable
  foundation but still needs manageable development or role-specific
  experience.

target_role_families:
- longer-term families aligned with the candidate's explicitly stated
  direction, including areas where the candidate may not yet be
  competitive.

The three lists are NOT the same thing.

Do not place a role family into competitive_role_families merely because
the candidate wants it.

Do not keep a candidate trapped in their historical profession when they
explicitly want to change career.

Use their:
- desired_next_work
- enjoyed_work
- avoid_work
- development_interests
- career_priorities

to interpret direction, while using work history as evidence of current
competitiveness.

CONSERVATIVE EVIDENCE RULE

Distinguish carefully between:

"has professional experience doing X"

and

"has transferable experience that could help with X"

and

"is interested in learning X".

These three statements must never be treated as equivalent.
""".strip()
