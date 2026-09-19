import pytest
from tests.semantic_shadow_batch_002_replay import compare_all, report, observed_cases


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import socket
    from services import database
    def deny(*args,**kwargs): raise AssertionError('Offline replay only')
    monkeypatch.setattr(socket.socket,'connect',deny)
    monkeypatch.setattr(socket,'getaddrinfo',deny)
    monkeypatch.setattr(database,'get_connection',deny)


def test_reported_pairs_and_agreement_not_model_accuracy():
    result = report()
    assert (result['total'],result['relation_agreement'],result['coverage_agreement'],result['dual_axis_agreement']) == (14,10,11,9)
    assert len(result['rows']) == 12
    assert {r['case_id'] for r in result['rows'] if r['changed']} == {'SE14','SE18','SE19','SE44','AV02'}


def test_se18_changes_satisfaction_and_proof_action_not_strength_or_category():
    row = next(r for r in compare_all() if r['case_id'] == 'SE18')
    a,b = row['reference'],row['observed_real_ai']
    assert a['requirements']['need']['assessment'] == 'transferable'
    assert a['requirements']['need']['satisfied'] is True
    assert b['requirements']['need']['assessment'] == 'evidence_missing'
    assert b['requirements']['need']['satisfied'] is False
    assert a['strength'] == b['strength'] == 'viable'
    assert a['category'] == b['category'] == 'skip_for_now'
    assert a['how_to_prove'] != b['how_to_prove']
    assert not a['add_evidence'] and b['add_evidence']
    assert row['impact'] == 'PRODUCT_DECISION_CHANGE'


@pytest.mark.parametrize('case_id',['SE14','SE19','SE44','AV02'])
def test_other_differences_preserve_current_proof_contract(case_id):
    row = next(r for r in compare_all() if r['case_id'] == case_id)
    assert row['changed'] == ['semantic']
    assert row['impact'] == 'EXPLANATION_ONLY'
    if case_id == 'AV02':
        for side in ('reference','observed_real_ai'):
            need = row[side]['requirements']['release']
            assert need['evidence_requirement'] == 'direct_required' and not need['satisfied']
            assert need['reason'] == 'direct_evidence_required'


@pytest.mark.parametrize('value',[None,'high','medium','low'])
@pytest.mark.parametrize('blocker',[False,True])
def test_no_optimistic_promotion_and_context_controls(value,blocker):
    for row in compare_all(value_context=value,blocker=blocker):
        a,b = row['reference'],row['observed_real_ai']
        for key in ('strength','eligibility','blockers','category','value','value_confidence'):
            assert a[key] == b[key]
        if blocker:
            assert b['strength'] == b['category'] == 'ineligible'
        for key, need in b['requirements'].items():
            prior = a['requirements'][key]
            if need['assessment'] == 'proven': assert prior['assessment'] == 'proven'
            assert need['assessment'] != 'gap'
            if need['satisfied']: assert prior['satisfied']
            assert need['temporal_result'] == prior['temporal_result'] == 'not_applicable'
