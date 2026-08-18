import json
from dataclasses import asdict

from models.candidate import Candidate
from models.career_objective import CareerObjective


def build_objective_profile_prompt(
    candidate: Candidate,
    objective: CareerObjective,
) -> str:
    candidate_json = json.dumps(
        asdict(candidate),
        ensure_ascii=False,
        indent=2,
    )

    objective_json = json.dumps(
        asdict(objective),
        ensure_ascii=False,
        indent=2,
    )

    return f"""
You are a career strategy analyst.

Your task is to create a goal-specific professional profile.

The candidate has a complete Master Career Profile containing their
full professional history.

The active Career Objective describes where the candidate wants to go
NOW.

Do not treat every historical role as part of the current search
direction.

Use the objective first, then inspect the candidate's full history and
select only the professional evidence that is useful for achieving that
objective.

Candidate Master Career Profile:

{candidate_json}

Active Career Objective:

{objective_json}

Build an Objective Profile that answers:

- Which role families aligned with this objective can the candidate
  realistically compete for now?
- Which aligned role families are credible bridge opportunities?
- Which aligned role families are longer-term targets?
- Which proven capabilities are relevant to this objective?
- Which transferable capabilities are useful for this objective?
- Which developing capabilities matter for this objective?
- Which tools and domains are relevant?
- Which historical experiences contain useful evidence?
- What important gaps remain?
- What development priorities would most improve the candidate's
  position toward this objective?

IMPORTANT PRINCIPLE

Historical experience is evidence, not direction.

For example, if a candidate previously worked in retail,
manufacturing or hospitality but now wants to move into technical
support, those historical role families must NOT automatically appear
as competitive role families.

However, useful evidence from those jobs may still be selected, such as:
- prioritisation;
- customer escalation handling;
- process monitoring;
- troubleshooting;
- quality control;
- team coordination.

COMPETITIVE ROLE FAMILIES

Only include role families that satisfy BOTH:

1. they are aligned with the active objective;
2. the candidate has enough relevant evidence to compete now.

BRIDGE ROLE FAMILIES

Include objective-aligned roles where the candidate has a credible
foundation but still has manageable gaps.

TARGET ROLE FAMILIES

Include objective-aligned longer-term directions where larger gaps may
still exist.

Do not place an unrelated historical profession in any of these three
lists merely because the candidate once worked in it.

RELEVANT EXPERIENCE IDS

Return only source_experience_id values from the candidate's
professional_experiences.

Select an experience when it contains evidence that materially supports
the active objective.

A historical job can be relevant without its original role family being
part of the current career direction.

DEVELOPMENT

development_gaps:
Important missing capabilities, tools, domain exposure or experience
that reduce competitiveness for the active objective.

development_priorities:
The highest-value areas to improve next.

Prioritise things that:
- recur across plausible target roles;
- are realistically learnable;
- build on the candidate's existing evidence;
- materially improve competitiveness.

Do not treat a course or basic knowledge as professional experience.

Do not invent evidence.

Return only valid JSON using exactly this structure:

{{
    "competitive_role_families": [],
    "bridge_role_families": [],
    "target_role_families": [],

    "relevant_proven_capabilities": [],
    "relevant_transferable_capabilities": [],
    "relevant_developing_capabilities": [],

    "relevant_tools": [],
    "relevant_domains": [],
    "relevant_strengths": [],

    "relevant_experience_ids": [],

    "development_gaps": [],
    "development_priorities": []
}}

Do not include markdown.
Do not include any text outside the JSON.
""".strip()
