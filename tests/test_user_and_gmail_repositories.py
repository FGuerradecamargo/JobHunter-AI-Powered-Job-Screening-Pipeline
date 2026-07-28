from models.gmail_connection import GmailConnection
from services.candidate_repository import CandidateRepository
from services.database import initialize_database
from services.gmail_connection_repository import (
    GmailConnectionRepository,
)
from services.user_repository import UserRepository

from cryptography.fernet import Fernet

from services.token_encryption_service import (
    TokenEncryptionService,
)


def test_create_user_and_save_gmail_connection():
    initialize_database()

    candidates = CandidateRepository().list_all()
    assert candidates

    candidate = candidates[0]

    user_repository = UserRepository()
    gmail_repository = GmailConnectionRepository()

    existing_user = user_repository.get_by_email(
        "repository-test@example.com"
    )

    if existing_user is None:
        user = user_repository.create(
            email="repository-test@example.com",
            display_name="Repository Test",
        )
    else:
        user = existing_user

    if user.candidate_id is None:
        user_repository.link_candidate(
            user_id=user.id,
            candidate_id=candidate.id,
        )

    connection = GmailConnection(
        user_id=user.id,
        gmail_address="repository-test@gmail.com",
        refresh_token="not-a-real-token",
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly"
        ],
    )

    gmail_repository.save(connection)

    saved_connection = gmail_repository.get_by_user_id(
        user.id
    )

    assert saved_connection is not None
    assert (
        saved_connection.gmail_address
        == "repository-test@gmail.com"
    )
    assert saved_connection.connection_status == "connected"
    assert saved_connection.scopes == [
        "https://www.googleapis.com/auth/gmail.readonly"
    ]

    assert (
            saved_connection.refresh_token
            == "not-a-real-token"
    )