from dataclasses import replace
from unittest.mock import Mock

import pytest

from models.candidate import Candidate
from models.company_interview import ConfirmedCompanyAnswer, V3_VERSION, V3_QUESTIONS
from services.candidate_repository import CandidateRepository
from services.candidate_onboarding_repository import CandidateOnboardingRepository
from services.company_interview import start_interview, answer, resume_interview


@pytest.fixture
def repo():
    for cid in ('a', 'b'):
        CandidateRepository().save(Candidate(cid, 'Synthetic', '', '', ''))
    return CandidateOnboardingRepository()


def begin(repo):
    repo.begin_company_interview(candidate_id='a', experience_id='draft', company='Synthetic',
                                 start_date='2020-01', end_date=None)


def response(index, mode='text'):
    return ConfirmedCompanyAnswer(f'q{index}', V3_QUESTIONS[index-1], mode,
        '' if mode == 'skip' else f'Source answer {index}', mode == 'skip', V3_VERSION, V3_VERSION)


def test_draft_reused_hidden_and_restored_after_session_loss(repo):
    begin(repo)
    begin(repo)
    repo.save_company_answer(candidate_id='a', experience_id='draft', answer=response(1))
    repo.save_company_answer(candidate_id='a', experience_id='draft', answer=response(1))
    assert repo.list_work_experiences('a') == []
    restored = resume_interview('new-browser-scope', 'a', CandidateOnboardingRepository())
    assert restored['id'] == 'draft'
    assert restored['answers'][0].confirmed_text == 'Source answer 1'
    assert restored['stage'] == 'question'
    assert repo.get_company_draft('b', 'draft') is None
    assert resume_interview('other', 'b', repo) is None


def test_four_core_responses_required_and_skips_are_unknown(repo):
    begin(repo)
    for i in range(1, 4):
        repo.save_company_answer(candidate_id='a', experience_id='draft', answer=response(i))
    with pytest.raises(ValueError, match='Incomplete'):
        repo.finalize_company_interview(candidate_id='a', experience_id='draft')
    assert repo.get_company_draft('a') is not None
    repo.save_company_answer(candidate_id='a', experience_id='draft', answer=response(4, 'skip'))
    repo.finalize_company_interview(candidate_id='a', experience_id='draft')
    experience = repo.list_work_experiences('a')[0]
    assert '[Q4]' not in experience.day_to_day_narrative
    assert len(experience.confirmed_interview_answers) == 4
    assert repo.get_company_draft('a') is None
    with pytest.raises(ValueError):
        repo.save_company_answer(candidate_id='a', experience_id='draft', answer=response(1))


def test_owner_version_and_concurrent_answer_are_guarded(repo):
    begin(repo)
    with pytest.raises(ValueError):
        repo.save_company_answer(candidate_id='b', experience_id='draft', answer=response(1))
    with pytest.raises(ValueError):
        repo.finalize_company_interview(candidate_id='b', experience_id='draft')
    repo.save_company_answer(candidate_id='a', experience_id='draft', answer=response(1))
    with pytest.raises(ValueError, match='already confirmed'):
        repo.save_company_answer(candidate_id='a', experience_id='draft', answer=replace(response(1), confirmed_text='Other tab'))
    assert repo.list_company_answers('a', 'draft')[0].confirmed_text == 'Source answer 1'


def test_start_persists_and_failed_write_does_not_advance(repo, monkeypatch):
    draft = start_interview('scope', 'a', 'Synthetic', '2020-01', None, repository=repo)
    assert repo.get_company_draft('a')['id'] == draft['id']
    assert start_interview('scope', 'a', 'Synthetic', '2020-01', None, repository=repo)['id'] == draft['id']
    monkeypatch.setattr(repo, 'save_company_answer', Mock(side_effect=RuntimeError('Synthetic DB failure')))
    with pytest.raises(RuntimeError):
        answer(draft, 'scope', 'text', 'My source', repository=repo)
    assert draft['answers'] == []
    assert draft['stage'] == 'memory'


def test_finalization_rolls_back_partial_writes(repo, monkeypatch):
    begin(repo)
    original = repo._write_answer
    def fail(connection, cid, eid, item):
        original(connection, cid, eid, item)
        if item.question_id == 'q2':
            raise RuntimeError('Synthetic failure')
    monkeypatch.setattr(repo, '_write_answer', fail)
    with pytest.raises(RuntimeError):
        repo.finalize_company_interview(candidate_id='a', experience_id='draft', answers=[response(i) for i in range(1, 5)])
    assert repo.list_company_answers('a', 'draft') == []
    assert repo.get_company_draft('a') is not None


def test_legacy_schema_upgrade_is_idempotent_and_keeps_confirmed_rows():
    import sqlite3
    from services.database import create_company_interview_schema
    with sqlite3.connect(':memory:') as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('CREATE TABLE candidate_work_experiences (id TEXT PRIMARY KEY, candidate_id TEXT)')
        connection.execute("INSERT INTO candidate_work_experiences VALUES ('legacy', 'a')")
        create_company_interview_schema(connection)
        create_company_interview_schema(connection)
        row = connection.execute('SELECT * FROM candidate_work_experiences').fetchone()
        assert row['onboarding_status'] == 'confirmed'
        assert row['onboarding_interview_version'] is None


def test_postgres_migration_is_additive(monkeypatch):
    from services import database
    connection = Mock()
    monkeypatch.setattr(database, 'is_postgres', lambda: True)
    monkeypatch.setattr(database, '_enable_server_only_row_level_security', Mock())
    database.create_company_interview_schema(connection)
    statements = [call.args[0] for call in connection.execute.call_args_list]
    assert any("ADD COLUMN IF NOT EXISTS onboarding_status TEXT NOT NULL DEFAULT 'confirmed'" in sql for sql in statements)
    assert any('ADD COLUMN IF NOT EXISTS onboarding_interview_version TEXT' in sql for sql in statements)
    assert not any(sql.lstrip().upper().startswith(('DROP ', 'DELETE ', 'TRUNCATE ')) for sql in statements)
