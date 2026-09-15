from __future__ import annotations

from models.company import Company, MonitoredCompany
from models.user_context import UserContext
from services.admin_access_session import AdminAccessSession
from services.database import get_connection, utc_now


class MonitoredCompanyRepository:
    def __init__(
        self, context: UserContext, *, admin_access: AdminAccessSession | None = None,
    ) -> None:
        self.context = context
        self.admin_access = admin_access

    def _authorize(self, connection, candidate_id: str) -> None:
        context = self.context
        owner = connection.execute(
            "SELECT candidate_id FROM users WHERE id = ?", (context.active_user.id,),
        ).fetchone()
        actor = connection.execute(
            "SELECT access_level FROM users WHERE id = ?", (context.authenticated_user.id,),
        ).fetchone()
        if (
            actor is None or owner is None or not candidate_id
            or candidate_id != owner["candidate_id"]
            or candidate_id != context.active_user.candidate_id
        ):
            raise PermissionError("Monitored companies are unavailable for this account.")
        if context.is_viewing_as and (
            actor["access_level"] != "admin"
            or self.admin_access is None
            or self.admin_access.get_authorized_target(
                authenticated_user_id=context.authenticated_user.id
            ) != context.active_user.id
        ):
            raise PermissionError("Administrative reauthentication is required.")

    def monitor_company(self, candidate_id: str, company_id: str) -> None:
        now = utc_now()
        with get_connection() as connection:
            self._authorize(connection, candidate_id)
            if connection.execute("SELECT 1 FROM companies WHERE id = ?", (company_id,)).fetchone() is None:
                raise ValueError("Company is unavailable.")
            connection.execute(
                """
                INSERT INTO candidate_monitored_companies (
                    candidate_id, company_id, active, created_at, updated_at
                ) VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(candidate_id, company_id) DO UPDATE SET
                    active = 1, updated_at = excluded.updated_at
                """, (candidate_id, company_id, now, now),
            )

    def stop_monitoring_company(self, candidate_id: str, company_id: str) -> None:
        with get_connection() as connection:
            self._authorize(connection, candidate_id)
            connection.execute(
                """UPDATE candidate_monitored_companies SET active = 0, updated_at = ?
                   WHERE candidate_id = ? AND company_id = ? AND active = 1""",
                (utc_now(), candidate_id, company_id),
            )

    def list_monitored_companies(self, candidate_id: str) -> list[MonitoredCompany]:
        with get_connection() as connection:
            self._authorize(connection, candidate_id)
            rows = connection.execute(
                """
                SELECT c.*, m.created_at AS monitored_created_at, m.updated_at AS monitored_updated_at
                FROM candidate_monitored_companies m
                JOIN companies c ON c.id = m.company_id
                WHERE m.candidate_id = ? AND m.active = 1
                ORDER BY c.normalized_name, c.id
                """, (candidate_id,),
            ).fetchall()
        results = []
        for row in rows:
            values = dict(row)
            created = values.pop("monitored_created_at")
            updated = values.pop("monitored_updated_at")
            results.append(MonitoredCompany(candidate_id, Company(**values), True, created, updated))
        return results
