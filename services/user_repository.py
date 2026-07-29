from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from models.app_user import AppUser
from services.database import get_connection


class UserRepository:
    def create(
        self,
        email: str,
        display_name: str,
        candidate_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AppUser:
        normalized_email = email.strip().lower()
        normalized_name = display_name.strip()

        if not normalized_email:
            raise ValueError("Email is required.")

        if not normalized_name:
            raise ValueError("Display name is required.")

        resolved_user_id = user_id or uuid4().hex
        now = datetime.now(timezone.utc).isoformat()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (
                    id,
                    email,
                    display_name,
                    candidate_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_user_id,
                    normalized_email,
                    normalized_name,
                    candidate_id,
                    now,
                    now,
                ),
            )

        return AppUser(
            id=resolved_user_id,
            email=normalized_email,
            display_name=normalized_name,
            candidate_id=candidate_id,
        )

    def get_by_id(
        self,
        user_id: str,
    ) -> Optional[AppUser]:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    email,
                    display_name,
                    candidate_id
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

        return self._row_to_user(row)

    def get_by_email(
        self,
        email: str,
    ) -> Optional[AppUser]:
        normalized_email = email.strip().lower()

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    email,
                    display_name,
                    candidate_id
                FROM users
                WHERE email = ?
                """,
                (normalized_email,),
            ).fetchone()

        return self._row_to_user(row)

    def get_by_candidate_id(
        self,
        candidate_id: str,
    ) -> Optional[AppUser]:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    email,
                    display_name,
                    candidate_id
                FROM users
                WHERE candidate_id = ?
                """,
                (candidate_id,),
            ).fetchone()

        return self._row_to_user(row)

    def link_candidate(
        self,
        user_id: str,
        candidate_id: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()

        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET
                    candidate_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    candidate_id,
                    now,
                    user_id,
                ),
            )

        if cursor.rowcount == 0:
            raise ValueError(
                f"User not found: {user_id}"
            )

    @staticmethod
    def _row_to_user(
        row,
    ) -> Optional[AppUser]:
        if row is None:
            return None

        return AppUser(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            candidate_id=row["candidate_id"],
        )

    def list_all(
            self,
    ) -> list[AppUser]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    email,
                    display_name,
                    candidate_id
                FROM users
                ORDER BY display_name ASC
                """
            ).fetchall()

        return [
            self._row_to_user(row)
            for row in rows
            if row is not None
        ]