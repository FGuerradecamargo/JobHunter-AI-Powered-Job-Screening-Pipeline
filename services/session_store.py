from __future__ import annotations


def ensure_session_table_with_connection(
    connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
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
