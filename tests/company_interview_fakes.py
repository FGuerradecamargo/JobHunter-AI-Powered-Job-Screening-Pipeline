"""Synthetic deterministic responses; no transport or credentials."""
import json
from services.company_reflection import FIELDS
from models.company_interview import ADAPTIVE_QUESTIONS

SCENARIOS = {
    'support': [
        'I check emails and previous shift notes at the BPO.',
        'I work on customer tickets and handle refunds and credits.',
        'Customers and colleagues bring ticket questions.',
        'I check logs and the backend to correct errors.',
        'I use Bliss/Chronicle, Jira, the Knowledge Base and SQL occasionally.',
        'We check ticket accuracy and I track my own workload.',
        'I correct routine errors and escalate to the TL or Engineering.',
        'Completed tickets and corrected refunds; otherwise they remain waiting.',
    ],
    'electrician': ['I arrive at site.', 'I plan the work.', 'The site supervisor brings plans.',
        'I investigate electrical faults.', 'I use electrical drawings, a multimeter and hand tools.',
        'I perform safety checks.', 'Changes require supervisor approval.', 'Tested circuits are ready.'],
    'nurse': ['I receive handover.', 'I visit patients.', 'Patients and colleagues need care information.',
        'I follow escalation procedures.', 'I use clinical records and clinical equipment.',
        'Medication and safety procedures guide checks.', 'I escalate beyond my authorization.', 'Care is documented.'],
    'warehouse': ['I check orders.', 'I move pallets.', 'Dispatch needs packed orders.',
        'I report damaged items.', 'I use a scanner and handling equipment.',
        'We check throughput, accuracy and safety.', 'I escalate equipment faults.', 'Orders are ready for dispatch.'],
    'concise': ['I check work.'] * 8,
}


def response(request, dimension=None, status='SUFFICIENT'):
    first = next((s for s in request['sources'] if not s['skipped']), None)
    interpretation = {field: [] for field in FIELDS}
    if first:
        interpretation['understood'] = [dict(text=first['text'],
            support=[dict(question_id=first['question_id'], quote=first['text'])],
            uncertainty='Candidate account of this experience; not independently verified.')]
    # These are frozen fake judgments, not runtime keyword inference.
    if first and first['text'] == SCENARIOS['support'][0]:
        for field, text, index in [
            ('function', 'Customer service', 1), ('role_family', 'Customer operations', 1),
            ('summary', 'Customer ticket support in a BPO context.', 0),
            ('capabilities', 'Routine error correction with escalation.', 6),
            ('tools', 'Occasional SQL use, not established expertise.', 4),
            ('contexts', 'BPO', 0), ('stakeholders', 'Customers and colleagues', 2),
            ('observed_work_patterns', 'Checks logs before correcting errors.', 3),
        ]:
            source = request['sources'][index]
            interpretation[field] = [dict(text=text,
                support=[dict(question_id=source['question_id'], quote=source['text'])],
                uncertainty='Draft interpretation limited to this stated experience.')]
    coverage = dict.fromkeys(ADAPTIVE_QUESTIONS, status)
    if dimension:
        coverage[dimension] = 'INSUFFICIENT'
    return dict(interpretation=interpretation, coverage=coverage, material_missing_dimension=dimension)


class FakeReflection:
    def __init__(self, dimension=None, status='SUFFICIENT', fail=False):
        self.prompts = []
        self.dimension, self.status, self.fail = dimension, status, fail

    def generate(self, prompt):
        self.prompts.append(prompt)
        if self.fail:
            raise RuntimeError('PRIVATE PROVIDER RESPONSE')
        request = json.loads(prompt.split('SOURCE DATA:\n', 1)[1])
        return json.dumps(response(request, self.dimension, self.status))
