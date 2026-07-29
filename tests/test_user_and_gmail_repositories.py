from cryptography.fernet import Fernet

from models.gmail_connection import GmailConnection
from services.database import initialize_database
from services.gmail_connection_repository import (
    GmailConnectionRepository,
)
from services.token_encryption_service import (
    TokenEncryptionService,
)
from services.user_repository import UserRepository


def test_create_user_and_save_gmail_connection():
    initialize_database()

    user_repository = UserRepository()

    encryption_service = TokenEncryptionService(
        encryption_key=Fernet.generate_key().decode()
    )

    gmail_repository = GmailConnectionRepository(
        token_encryption_service=encryption_service
    )

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

    connection = GmailConnection(
        user_id=user.id,
        gmail_address="repository-test@gmail.com",
        refresh_token="not-a-real-token",
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly"
        ],
    )

    gmail_repository.save(connection)

    saved_connection = (
        gmail_repository.get_by_user_id(
            user.id
        )
    )

    assert saved_connection is not None

    assert (
        saved_connection.gmail_address
        == "repository-test@gmail.com"
    )

    assert (
        saved_connection.refresh_token
        == "not-a-real-token"
    )

    assert (
        saved_connection.connection_status
        == "connected"
    )

    assert saved_connection.scopes == [
        "https://www.googleapis.com/auth/gmail.readonly"
    ]

