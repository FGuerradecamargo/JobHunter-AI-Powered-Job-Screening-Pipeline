from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional
from uuid import uuid4

from models.app_user import AppUser
from models.candidate import Candidate
from services.candidate_repository import CandidateRepository
from services.database import get_connection
from services.user_repository import UserRepository


class AuthService:
    ITERATIONS = 310_000

    def __init__(self) -> None:
        self.user_repository = UserRepository()
        self.candidate_repository = CandidateRepository()

    @classmethod
    def hash_password(
        cls,
        password: str,
    ) -> str:
        if len(password) < 8:
            raise ValueError(
                "Password must contain at least 8 characters."
            )

        salt = os.urandom(16)

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            cls.ITERATIONS,
        )

        return (
            f"{cls.ITERATIONS}$"
            f"{salt.hex()}$"
            f"{password_hash.hex()}"
        )

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
        password_hash = self.hash_password(password)

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET
                    password_hash = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    password_hash,
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
                WHERE email = ?
                """,
                (normalized_email,),
            ).fetchone()

        if row is None:
            return None

        if not self.verify_password(
            password,
            row["password_hash"],
        ):
            return None

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
                SET password_hash = ?
                WHERE id = ?
                """,
                (
                    password_hash,
                    user.id,
                ),
            )

        return self.user_repository.get_by_id(
            user.id
        )
