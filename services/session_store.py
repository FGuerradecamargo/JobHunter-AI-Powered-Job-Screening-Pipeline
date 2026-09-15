from __future__ import annotations

import sqlite3

from services.database import is_postgres


def ensure_session_table_with_connection(
    connection,
) -> None:
    if is_postgres():
        connection.execute("SELECT pg_advisory_xact_lock(731302)")
    elif isinstance(connection, sqlite3.Connection) and not connection.in_transaction:
        connection.execute("BEGIN IMMEDIATE")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_activity_at TEXT NOT NULL,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )

    if is_postgres():
        connection.execute(
            """
            ALTER TABLE user_sessions
            ADD COLUMN IF NOT EXISTS last_activity_at TEXT
            """
        )
    else:
        columns = connection.execute(
            "PRAGMA table_info(user_sessions)"
        ).fetchall()
        column_names = {
            str(row["name"] if hasattr(row, "keys") else row[1])
            for row in columns
        }
        if "last_activity_at" not in column_names:
            connection.execute(
                """
                ALTER TABLE user_sessions
                ADD COLUMN last_activity_at TEXT
                """
            )

    connection.execute(
        """
        UPDATE user_sessions
        SET last_activity_at = created_at
        WHERE
            last_activity_at IS NULL
            OR TRIM(last_activity_at) = ''
        """
    )


def revoke_user_sessions_with_connection(
    connection,
    user_id: str,
) -> int:
    normalized_user_id = str(
        user_id or ""
    ).strip()

    if not normalized_user_id:
        raise ValueError(
            "User ID is required."
        )

    ensure_session_table_with_connection(
        connection
    )

    cursor = connection.execute(
        """
        DELETE FROM user_sessions
        WHERE user_id = ?
        """,
        (
            normalized_user_id,
        ),
    )

    return int(
        cursor.rowcount
    )
