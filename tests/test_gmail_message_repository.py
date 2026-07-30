from uuid import uuid4

from services.database import initialize_database
from services.gmail_message_repository import (
    GmailMessageRepository,
)
from services.user_repository import UserRepository


def test_registers_message_only_once():
    initialize_database()

    unique_value = uuid4().hex

    user = UserRepository().create(
        email=f"{unique_value}@example.com",
        display_name="Gmail Message Test",
    )

    repository = GmailMessageRepository()

    first_registration = repository.register_if_new(
        user_id=user.id,
        gmail_message_id=f"message-{unique_value}",
        gmail_thread_id=f"thread-{unique_value}",
    )

    second_registration = repository.register_if_new(
        user_id=user.id,
        gmail_message_id=f"message-{unique_value}",
        gmail_thread_id=f"thread-{unique_value}",
    )

    assert first_registration is True
    assert second_registration is False

    counts = repository.count_by_status(
        user.id
    )

    assert counts["pending"] == 1