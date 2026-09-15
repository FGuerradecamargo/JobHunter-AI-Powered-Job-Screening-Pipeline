from __future__ import annotations

from uuid import uuid4

from models.company import Company
from services.company_normalization import company_name, company_domain, public_careers_url
from services.database import get_connection, utc_now


class CompanyRepository:
    """Shared company data; no candidate relationships are returned here."""

    def get_or_create_company(
        self, canonical_name: str, *, domain: str | None = None,
        careers_url: str | None = None,
    ) -> Company:
        name, normalized = company_name(canonical_name)
        domain = company_domain(domain)
        careers_url = public_careers_url(careers_url)
        now = utc_now()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO companies (
                    id, canonical_name, normalized_name, domain, careers_url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(normalized_name) DO NOTHING
                """,
                (uuid4().hex, name, normalized, domain, careers_url, now, now),
            )
            row = connection.execute(
                "SELECT * FROM companies WHERE normalized_name = ?", (normalized,),
            ).fetchone()
            if domain and row["domain"] and domain != row["domain"]:
                raise ValueError("Company name has a conflicting domain; explicit review is required.")
        return Company(**dict(row))

    def find_company(self, canonical_name: str) -> Company | None:
        _, normalized = company_name(canonical_name)
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM companies WHERE normalized_name = ?", (normalized,),
            ).fetchone()
        return Company(**dict(row)) if row else None

    def get(self, company_id: str) -> Company | None:
        with get_connection() as connection:
            row = connection.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        return Company(**dict(row)) if row else None
