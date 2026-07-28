from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GmailConnection:
    user_id: str
    gmail_address: str
    refresh_token: str
    scopes: list[str]
    access_token: Optional[str] = None
    token_expiry: Optional[str] = None
    last_history_id: Optional[str] = None
    last_sync_at: Optional[str] = None
    connection_status: str = "connected"