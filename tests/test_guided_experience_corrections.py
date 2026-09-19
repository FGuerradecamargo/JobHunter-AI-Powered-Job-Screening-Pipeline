from dataclasses import replace
from unittest.mock import Mock

import pytest

from models.candidate import Candidate
from models.candidate_onboarding import CandidateOnboarding
from models.company_interview import ConfirmedCompanyAnswer, QUESTIONS, FINAL_QUESTION
from services.candidate_repository import CandidateRepository
from services.candidate_onboarding_repository import CandidateOnboardingRepository
from services.ai.candidate_profile_prompt_builder import build_candidate_profile_prompt


@pytest.fixture
def source():
    for owner in ('owner', 'other'):
        CandidateRepository().save(Candidate(id=owner, name='Fixture', current_role='',
            current_level='', professional_summary=''))
    repo = CandidateOnboardingRepository()
    answers = [ConfirmedCompanyAnswer(f'q{i}', q, 'text', 'ORIGINAL_ACCOUNT', False)
        for i, q in enumerate(QUESTIONS, 1)]
    answers.append(ConfirmedCompanyAnswer('final', FINAL_QUESTION, 'skip', '', True,
        source_kind='FINAL_OPEN'))
    repo.confirm_company_interview(candidate_id='owner', company='Fixture', start_date='2020',
        end_date=None, answers=answers, experience_id='experience')
    return repo, repo.list_work_experiences('owner')[0]


def prompt(repo):
    return build_candidate_profile_prompt(CandidateOnboarding('owner'), repo.list_work_experiences('owner'))


def test_confirmed_edit_is_next_generation_source_and_history_survives(source):
    repo, original = source
    revised = replace(original, career_story='USER_CORRECTED_STORY', day_to_day_narrative='USER_CORRECTED_DAY')
    repo.update_work_experience(revised, confirmed_source_edit=True)
    rendered = prompt(repo)
    assert 'USER_CORRECTED_STORY' in rendered and 'USER_CORRECTED_DAY' in rendered
    assert 'ORIGINAL_ACCOUNT' not in rendered
    history = repo.list_company_answers('owner', original.id, include_history=True)
    assert len(history) == 10
    assert any(a.confirmed_text == 'ORIGINAL_ACCOUNT' for a in history)
    assert history[-1].source_kind == 'USER_CONFIRMED_EDIT'
    assert all(a.source_kind != 'AI_INTERPRETATION' for a in history)


def test_unconfirmed_edit_does_not_change_authoritative_source(source):
    repo, original = source
    draft = replace(original, career_story='UNCONFIRMED_DRAFT')
    assert 'UNCONFIRMED_DRAFT' not in prompt(repo)
    with pytest.raises(ValueError, match='Confirm your source'):
        repo.update_work_experience(draft)
    assert 'ORIGINAL_ACCOUNT' in prompt(repo)
    assert repo.list_work_experiences('owner')[0].career_story == original.career_story


def test_latest_correction_wins_without_erasing_earlier_correction(source):
    repo, original = source
    for text in ('FIRST_CORRECTION', 'LATEST_CORRECTION'):
        repo.update_work_experience(replace(original, career_story=text, day_to_day_narrative=''),
            confirmed_source_edit=True)
    assert 'LATEST_CORRECTION' in prompt(repo)
    assert 'FIRST_CORRECTION' not in prompt(repo) and 'ORIGINAL_ACCOUNT' not in prompt(repo)
    assert len(repo.list_company_answers('owner', original.id, include_history=True)) == 11


def test_foreign_candidate_cannot_correct_or_read_source(source):
    repo, original = source
    with pytest.raises(ValueError, match='not found for candidate'):
        repo.update_work_experience(replace(original, candidate_id='other', career_story='FOREIGN'),
            confirmed_source_edit=True)
    assert repo.list_company_answers('other', original.id, include_history=True) == []
    assert 'ORIGINAL_ACCOUNT' in prompt(repo)


def test_metadata_only_update_preserves_question_provenance(source):
    repo, original = source
    before = repo.list_company_answers('owner', original.id, include_history=True)
    repo.update_work_experience(replace(original, company='Corrected company'))
    assert repo.list_company_answers('owner', original.id, include_history=True) == before
    assert 'Corrected company' in prompt(repo)


def test_real_generation_service_receives_confirmed_source(source):
    from services.candidate_profile_generation_service import CandidateProfileGenerationService
    repo, original = source
    repo.save_onboarding(CandidateOnboarding('owner'))
    repo.update_work_experience(replace(original, career_story='CONFIRMED_NEW_ACCOUNT',
        day_to_day_narrative=''), confirmed_source_edit=True)
    llm = Mock()
    # Capture the real request, then stop before parsing; never instantiate a provider.
    llm.generate.side_effect = RuntimeError('end of fake capture')
    updates = Mock()
    updates.list_for_candidate.return_value = []
    service = CandidateProfileGenerationService(llm, repo, Mock(), updates)
    with pytest.raises(RuntimeError, match='end of fake capture'):
        service.generate('owner', 'Fixture')
    captured = llm.generate.call_args.args[0]
    assert 'CONFIRMED_NEW_ACCOUNT' in captured and 'ORIGINAL_ACCOUNT' not in captured


def test_pre_fix_saved_text_requires_confirmation_and_is_not_ignored(source):
    from services.database import get_connection
    repo, original = source
    # Simulate an old narrative edit saved before source corrections were supported.
    with get_connection() as connection:
        connection.execute('UPDATE candidate_work_experiences SET career_story = ?, '
            'day_to_day_narrative = ? WHERE id = ? AND candidate_id = ?',
            ('PRE_FIX_CORRECTION', '', original.id, 'owner'))
    loaded = repo.list_work_experiences('owner')[0]
    assert 'PRE_FIX_CORRECTION' not in prompt(repo)
    repo.update_work_experience(loaded, confirmed_source_edit=True)
    assert 'PRE_FIX_CORRECTION' in prompt(repo) and 'ORIGINAL_ACCOUNT' not in prompt(repo)
    repo.update_work_experience(loaded, confirmed_source_edit=True)
    assert len(repo.list_company_answers('owner', original.id, include_history=True)) == 10
