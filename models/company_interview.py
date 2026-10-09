"""Fixed recall questions, not capability assertions."""
from dataclasses import dataclass

V1_VERSION = 'company-interview-v1'
VERSION = 'company-interview-v2'
V2_VERSION = VERSION
V3_VERSION = 'company-interview-v3'
V4_VERSION = 'company-interview-v4'
V4_QUESTIONS = (
    'Imagine I start tomorrow in your role. What would I actually be doing day to day?',
    'What kinds of problems were you responsible for solving, and what decisions could you make yourself?',
    'Can you give me an example of something you handled particularly well, improved, solved, or helped achieve in this role?',
)
V4_ADAPTIVE_QUESTIONS = {
    'core_work': 'Which part of that work could you describe in more detail?',
    'judgment_responsibility': 'Which decisions in that situation were yours to make?',
    'evidence_contribution': 'What did you personally contribute in that example?',
    'tools_resources': 'What tools, systems or technologies did you use to do that?',
}
V3_QUESTIONS = (
    'Imagine I start tomorrow in your role. What would I actually be doing?',
    'What kinds of problems did you deal with, and what decisions were you responsible for?',
    'What tools, systems or technologies did you actually use?',
    'What changed because of your work, or what became different while you were there?',
)
V1_QUESTIONS = (
    'When you got to work, what did you usually do first?',
    'And after that? How did the day usually go?',
    'Who would usually come to you during the day? What did they need from you?',
    'When something went wrong, what usually happened? What did you do?',
    'When you were doing the job, what did you usually have open or in front of you?',
    'When something different came up, did you usually sort it out yourself or call someone? How did that work?',
    'Remember, I\u2019m starting tomorrow. Is there anything about this job I still haven\u2019t asked that you think I should know?',
)
QUESTIONS = (
    'When I get in tomorrow, what do I do first?',
    'And then? Take me through how the day usually goes from there.',
    'Who am I usually dealing with during the day, and what do they normally need from me?',
    'When something goes wrong, what usually happens? What do I do first? If an example comes to mind, tell me about it :D',
    'What am I actually going to use to do the job — systems, tools, machines, documents, equipment, whatever it is? Which ones do I really need to know, and what do I use them for?',
    'How do I know I’m doing the job right? What do people actually look at, check, measure or care about?',
    'What can I normally decide or fix on my own, and when do I need to bring someone else in?',
    'At the end of a good day, what have I actually got done? What would still be sitting there if I hadn’t done my job?',
)
FINAL_QUESTION = 'Remember, I start tomorrow. Is there anything else about the job I should know?'
CORRECTION_QUESTION = 'Anything here wrong or missing?'
ADAPTIVE_QUESTIONS = {
    'core_work': "Is there a big part of the job we still haven't actually talked about?",
    'context': "What kind of environment am I walking into tomorrow? What's important for me to understand about how the place works?",
    'stakeholders': "Is there anyone important I'll need to work with that we haven't talked about yet?",
    'tools_resources': "Is there anything I need to know how to use that we haven't talked about yet?",
    'problem_resolution': "When something doesn't go to plan, what usually happens next?",
    'concrete_evidence': 'Can you think of one time that actually happened? What happened?',
    'autonomy_escalation': "I'm still not totally sure what you handle yourself. What usually makes you bring someone else in?",
    'quality_standards': 'What do people actually use to tell whether the job was done well?',
    'outcomes_scale': 'Roughly how much of this are you dealing with — cases, customers, orders, projects, whatever makes sense in your job?',
    'work_patterns': 'Is there something you find yourself doing again and again to keep the work under control?',
}
ACKNOWLEDGEMENTS = ('Uhum.', 'Got it.', 'Okay.', 'Nice.', 'Right.', 'Got it.', 'Okay.', 'Right.')


@dataclass(frozen=True)
class ConfirmedCompanyAnswer:
    question_id: str
    question_text: str
    answer_mode: str
    confirmed_text: str
    skipped: bool
    interview_version: str = VERSION
    question_version: str = VERSION
    source_kind: str = 'FIXED_QUESTION'


def _validate_historical_answers(answers):
    if not answers or not all(isinstance(a, ConfirmedCompanyAnswer) for a in answers):
        raise ValueError('Incomplete interview.')
    version = answers[0].interview_version
    expected = {f'q{i + 1}': (text, 'FIXED_QUESTION') for i, text in
        enumerate(V1_QUESTIONS if version == V1_VERSION else QUESTIONS)}
    if version == VERSION:
        expected['final'] = (FINAL_QUESTION, 'FINAL_OPEN')
        expected['correction'] = (CORRECTION_QUESTION, 'REVIEW_CORRECTION')
    elif version != V1_VERSION:
        raise ValueError('Invalid interview version.')
    ids = [a.question_id for a in answers]
    required = set(expected) - {'correction'}
    adaptive = [qid for qid in ids if qid.startswith('adaptive_')]
    if len(set(ids)) != len(ids) or not required.issubset(ids) or len(adaptive) > 1:
        raise ValueError('Incomplete interview.')
    for dimension, text in ADAPTIVE_QUESTIONS.items():
        if version == VERSION:
            expected['adaptive_' + dimension] = (text, 'ADAPTIVE_QUESTION')
    for answer in answers:
        if (not isinstance(answer, ConfirmedCompanyAnswer)
                or expected.get(answer.question_id) != (answer.question_text, answer.source_kind)
                or answer.interview_version != version or answer.question_version != version
                or answer.answer_mode not in ('voice', 'text', 'skip')
                or answer.skipped != (answer.answer_mode == 'skip')
                or not isinstance(answer.confirmed_text, str)
                or len(answer.confirmed_text) > 20000
                or (answer.skipped and answer.confirmed_text != '')
                or (not answer.skipped and not answer.confirmed_text.strip())):
            raise ValueError('Invalid confirmed answer.')


def validate_single_answer(answer):
    if not isinstance(answer, ConfirmedCompanyAnswer):
        raise ValueError('Invalid confirmed answer.')
    questions = {V1_VERSION: V1_QUESTIONS, V2_VERSION: QUESTIONS, V3_VERSION: V3_QUESTIONS,
                 V4_VERSION: V4_QUESTIONS}
    if answer.interview_version not in questions:
        raise ValueError('Invalid interview version.')
    expected = {f'q{i + 1}': (text, 'FIXED_QUESTION')
                for i, text in enumerate(questions[answer.interview_version])}
    if answer.interview_version != V1_VERSION:
        adaptive = V4_ADAPTIVE_QUESTIONS if answer.interview_version == V4_VERSION else ADAPTIVE_QUESTIONS
        expected.update({'adaptive_' + key: (text, 'ADAPTIVE_QUESTION') for key, text in adaptive.items()})
        expected['correction'] = (CORRECTION_QUESTION, 'REVIEW_CORRECTION')
    if answer.interview_version == V2_VERSION:
        expected['final'] = (FINAL_QUESTION, 'FINAL_OPEN')
    if (expected.get(answer.question_id) != (answer.question_text, answer.source_kind)
            or answer.question_version != answer.interview_version
            or answer.answer_mode not in ('voice', 'text', 'skip')
            or answer.skipped != (answer.answer_mode == 'skip')
            or not isinstance(answer.confirmed_text, str) or len(answer.confirmed_text) > 20000
            or (answer.skipped and answer.confirmed_text != '')
            or (not answer.skipped and not answer.confirmed_text.strip())):
        raise ValueError('Invalid confirmed answer.')


def validate_answers(answers):
    if not answers:
        raise ValueError('Incomplete interview.')
    for answer in answers:
        validate_single_answer(answer)
    if answers[0].interview_version == V4_VERSION:
        validate_v4_partial_answers(answers)
        if not {'q1', 'q2', 'q3'}.issubset(a.question_id for a in answers):
            raise ValueError('Incomplete interview.')
        return
    if answers[0].interview_version != V3_VERSION:
        return _validate_historical_answers(answers)
    ids = [answer.question_id for answer in answers]
    if (any(answer.interview_version != V3_VERSION for answer in answers)
            or len(ids) != len(set(ids))
            or not {'q1', 'q2', 'q3', 'q4'}.issubset(ids)
            or sum(qid.startswith('adaptive_') for qid in ids) > 2):
        raise ValueError('Incomplete interview.')


def validate_v4_partial_answers(answers):
    """Validate durable V4 sources, including unfinished interviews."""
    for answer in answers:
        validate_single_answer(answer)
        if answer.interview_version != V4_VERSION:
            raise ValueError('Invalid interview version.')
    ids = [a.question_id for a in answers]
    if len(ids) != len(set(ids)) or sum(qid.startswith('adaptive_') for qid in ids) > 2:
        raise ValueError('Invalid V4 answer collection.')
    if any(qid.startswith('adaptive_') or qid == 'correction' for qid in ids):
        if not {'q1', 'q2', 'q3'}.issubset(ids):
            raise ValueError('Incomplete interview.')
