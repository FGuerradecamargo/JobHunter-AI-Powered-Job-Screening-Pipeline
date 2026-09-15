from __future__ import annotations

from uuid import uuid4

from models.company import CompanyJobSource
from services.company_normalization import public_careers_url, source_identifier
from services.database import get_connection, utc_now


def _source(row) -> CompanyJobSource:
    values = dict(row)
    values["enabled"] = bool(values["enabled"])
    return CompanyJobSource(**values)


class CompanySourceRepository:
    """Trusted backend registry. Never expose write methods as user actions."""

    def upsert_company_source(
        self, company_id: str, source_type: str, source_key: str, *,
        careers_url: str | None = None, enabled: bool = True,
    ) -> CompanyJobSource:
        source_type = source_identifier(source_type, source_type=True)
        source_key = source_identifier(source_key)
        careers_url = public_careers_url(careers_url)
        if not isinstance(enabled, bool):
            raise ValueError("Enabled must be a boolean.")
        now = utc_now()
        with get_connection() as connection:
            if connection.execute("SELECT 1 FROM companies WHERE id = ?", (company_id,)).fetchone() is None:
                raise ValueError("Company is unavailable.")
            connection.execute(
                """
                INSERT INTO company_job_sources (
                    id, company_id, source_type, source_key, careers_url, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id, source_type, source_key) DO UPDATE SET
                    careers_url = excluded.careers_url,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (uuid4().hex, company_id, source_type, source_key, careers_url, int(enabled), now, now),
            )
            row = connection.execute(
                """SELECT * FROM company_job_sources
                   WHERE company_id = ? AND source_type = ? AND source_key = ?""",
                (company_id, source_type, source_key),
            ).fetchone()
        return _source(row)

    def list_company_sources(self, company_id: str) -> list[CompanyJobSource]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM company_job_sources WHERE company_id = ? ORDER BY source_type, source_key",
                (company_id,),
            ).fetchall()
        return [_source(row) for row in rows]
