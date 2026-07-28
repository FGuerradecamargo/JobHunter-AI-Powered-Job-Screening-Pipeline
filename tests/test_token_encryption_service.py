import pytest
from cryptography.fernet import Fernet

from services.token_encryption_service import (
    TokenEncryptionService,
)


def test_encrypt_and_decrypt_token():
    encryption_key = Fernet.generate_key().decode()

    service = TokenEncryptionService(
        encryption_key=encryption_key
    )

    original_token = "example-refresh-token"

    encrypted_token = service.encrypt(
        original_token
    )

    assert encrypted_token != original_token

    decrypted_token = service.decrypt(
        encrypted_token
    )

    assert decrypted_token == original_token


def test_rejects_empty_value():
    encryption_key = Fernet.generate_key().decode()

    service = TokenEncryptionService(
        encryption_key=encryption_key
    )

    with pytest.raises(ValueError):
        service.encrypt("")

    with pytest.raises(ValueError):
        service.decrypt("")


def test_rejects_token_encrypted_with_another_key():
    first_service = TokenEncryptionService(
        encryption_key=Fernet.generate_key().decode()
    )

    second_service = TokenEncryptionService(
        encryption_key=Fernet.generate_key().decode()
    )

    encrypted_token = first_service.encrypt(
        "example-refresh-token"
    )

    with pytest.raises(ValueError):
        second_service.decrypt(
            encrypted_token
        )