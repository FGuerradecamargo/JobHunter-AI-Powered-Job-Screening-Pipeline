from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional
from uuid import uuid4

from models.app_user import AppUser
from models.candidate import Candidate
from services.candidate_repository import CandidateRepository
from services.database import get_connection, utc_now
from services.user_repository import UserRepository


class AuthService:
    ITERATIONS = 600_000
    MIN_PASSWORD_LENGTH = 15
    MAX_PASSWORD_LENGTH = 128

    def __init__(self) -> None:
        self.user_repository = UserRepository()
        self.candidate_repository = CandidateRepository()

    @classmethod
    def validate_password_policy(
        cls,
        password: str,
    ) -> None:
        if not isinstance(password, str):
            raise ValueError(
                "Password must be text."
            )

        if len(password) < cls.MIN_PASSWORD_LENGTH:
            raise ValueError(
                "Password must contain at least "
                f"{cls.MIN_PASSWORD_LENGTH} characters."
            )

        if len(password) > cls.MAX_PASSWORD_LENGTH:
            raise ValueError(
                "Password must contain at most "
                f"{cls.MAX_PASSWORD_LENGTH} characters."
            )

    @classmethod
    def _build_password_hash(
        cls,
        password: str,
        *,
        iterations: int,
    ) -> str:
        salt = os.urandom(16)

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )

        return (
            f"{iterations}$"
            f"{salt.hex()}$"
            f"{password_hash.hex()}"
        )

    @classmethod
    def hash_password(
        cls,
        password: str,
    ) -> str:
        cls.validate_password_policy(
            password
        )

        return cls._build_password_hash(
            password,
            iterations=cls.ITERATIONS,
        )

    @classmethod
    def needs_password_rehash(
        cls,
        stored_hash: str,
    ) -> bool:
        try:
            iterations_text, _, _ = (
                stored_hash.split("$")
            )

            iterations = int(
                iterations_text
            )

        except (
            AttributeError,
            TypeError,
            ValueError,
        ):
            return False

        return iterations < cls.ITERATIONS

    @classmethod
    def verify_password(
        cls,
        password: str,
        stored_hash: str,
    ) -> bool:
        if not stored_hash:
            return False

        try:
            iterations_text, salt_hex, hash_hex = (
                stored_hash.split("$")
            )

            iterations = int(iterations_text)
            salt = bytes.fromhex(salt_hex)
            expected_hash = bytes.fromhex(hash_hex)

        except (ValueError, TypeError):
            return False

        candidate_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )

        return hmac.compare_digest(
            candidate_hash,
            expected_hash,
        )

    def set_password(
            self,
            user_id: str,
            password: str,
    ) -> None:
        password_hash = self.hash_password(
            password
        )

        now = utc_now()

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET
                    password_hash = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    password_hash,
                    now,
                    user_id,
                ),
            )

        if cursor.rowcount == 0:
            raise ValueError(
                f"User not found: {user_id}"
            )

    def authenticate(
        self,
        email: str,
        password: str,
    ) -> Optional[AppUser]:
        normalized_email = email.strip().lower()

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    password_hash
                FROM users
                WHERE email = %s
                """,
                (normalized_email,),
            ).fetchone()

        if row is None:
            return None

        stored_hash = row[
            "password_hash"
        ]

        if not self.verify_password(
            password,
            stored_hash,
        ):
            return None

        if self.needs_password_rehash(
            stored_hash
        ):
            upgraded_hash = (
                self._build_password_hash(
                    password,
                    iterations=self.ITERATIONS,
                )
            )

            with get_connection() as connection:
                connection.execute(
                    """
                    UPDATE users
                    SET
                        password_hash = %s,
                        updated_at = %s
                    WHERE
                        id = %s
                        AND password_hash = %s
                    """,
                    (
                        upgraded_hash,
                        utc_now(),
                        row["id"],
                        stored_hash,
                    ),
                )

        return self.user_repository.get_by_id(
            row["id"]
        )

    def register(
        self,
        email: str,
        display_name: str,
        password: str,
    ) -> AppUser:
        normalized_email = email.strip().lower()
        normalized_name = display_name.strip()

        if not normalized_email:
            raise ValueError("Email is required.")

        if not normalized_name:
            raise ValueError("Name is required.")

        if self.user_repository.get_by_email(
            normalized_email
        ):
            raise ValueError(
                "An account with this email already exists."
            )

        password_hash = self.hash_password(password)

        candidate_id = f"candidate_{uuid4().hex}"

        candidate = Candidate(
            id=candidate_id,
            name=normalized_name,
            current_role="",
            current_level="",
            professional_summary="",
        )

        self.candidate_repository.save(candidate)

        user = self.user_repository.create(
            email=normalized_email,
            display_name=normalized_name,
            candidate_id=candidate_id,
            access_level="user",
        )

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE users
                SET
                    password_hash = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    password_hash,
                    utc_now(),
                    user.id,
                ),
            )

        return self.user_repository.get_by_id(
            user.id
        )
