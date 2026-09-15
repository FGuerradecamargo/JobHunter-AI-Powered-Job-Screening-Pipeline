from __future__ import annotations

from threading import Lock

from services.database import (
    get_connection,
    initialize_database,
)
from services.session_store import (
    ensure_session_table_with_connection,
)


_bootstrap_lock = Lock()
_bootstrap_complete = False


def bootstrap_application() -> None:
    global _bootstrap_complete

    if _bootstrap_complete:
        return

    with _bootstrap_lock:
        if _bootstrap_complete:
            return

        initialize_database()

        with get_connection() as connection:
            ensure_session_table_with_connection(
                connection
            )

        _bootstrap_complete = True
