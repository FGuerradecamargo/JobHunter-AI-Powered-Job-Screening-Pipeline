from __future__ import annotations

import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


class TokenEncryptionService:
    ENVIRONMENT_VARIABLE = "TOKEN_ENCRYPTION_KEY"

    def __init__(
        self,
        encryption_key: Optional[str] = None,
    ) -> None:
        resolved_key = (
            encryption_key
            or os.getenv(self.ENVIRONMENT_VARIABLE)
        )

        if not resolved_key:
            raise RuntimeError(
                "TOKEN_ENCRYPTION_KEY is not configured."
            )

        try:
            self._fernet = Fernet(
                resolved_key.encode("utf-8")
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                "TOKEN_ENCRYPTION_KEY is invalid."
            ) from error

    def encrypt(
        self,
        plain_text: str,
    ) -> str:
        if not plain_text:
            raise ValueError(
                "The value to encrypt cannot be empty."
            )

        encrypted_value = self._fernet.encrypt(
            plain_text.encode("utf-8")
        )

        return encrypted_value.decode("utf-8")

    def decrypt(
        self,
        encrypted_text: str,
    ) -> str:
        if not encrypted_text:
            raise ValueError(
                "The encrypted value cannot be empty."
            )

        try:
            decrypted_value = self._fernet.decrypt(
                encrypted_text.encode("utf-8")
            )
        except InvalidToken as error:
            raise ValueError(
                "The encrypted token is invalid or "
                "was encrypted with another key."
            ) from error

        return decrypted_value.decode("utf-8")