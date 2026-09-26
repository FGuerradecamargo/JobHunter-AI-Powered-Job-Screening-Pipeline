from __future__ import annotations

from dataclasses import asdict
import json

from models.company_profile import CompanyProfileSnapshot, CompanyPublicSource, CompanyClaim
from services.database import get_connection


class CompanyProfileRepository:
    """Server-only immutable snapshots; schema initialization is not a read-path side effect."""

    def version(self, company_id: str, version: int):
        with get_connection() as connection:
            row = connection.execute(
                "SELECT profile_json FROM company_profile_snapshots WHERE company_id = ? AND profile_version = ?",
                (company_id, version),
            ).fetchone()
        return self._from_json(row["profile_json"]) if row else None

    def current(
        self,
        company_id: str,
    ) -> CompanyProfileSnapshot | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT profile_json
                   FROM company_profile_snapshots
                   WHERE company_id = ?
                   ORDER BY profile_version DESC LIMIT 1""",
                (company_id,),
            ).fetchone()
        return (
            self._from_json(row["profile_json"])
            if row
            else None
        )

    def for_signature(
        self,
        company_id: str,
        source_signature: str,
    ) -> CompanyProfileSnapshot | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT profile_json
                   FROM company_profile_snapshots
                   WHERE company_id = ?
                     AND source_signature = ?
                     AND schema_version = ?
                   ORDER BY profile_version DESC LIMIT 1""",
                (
                    company_id,
                    source_signature,
                    "company-profile-v1",
                ),
            ).fetchone()
        return (
            self._from_json(row["profile_json"])
            if row
            else None
        )

    def save(
        self,
        profile: CompanyProfileSnapshot,
    ) -> None:
        raw = json.dumps(asdict(profile), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with get_connection() as connection:
            connection.execute(
                """INSERT INTO company_profile_snapshots
                   (company_id, profile_version, schema_version,
                    source_signature, supersedes_version,
                    profile_json, created_at)
                   SELECT ?, ?, ?, ?, ?, ?, ? WHERE
                     COALESCE((SELECT MAX(profile_version) FROM company_profile_snapshots
                               WHERE company_id = ?), 0) = ?
                   ON CONFLICT (company_id, profile_version) DO NOTHING""",
                (
                    profile.company_id,
                    profile.profile_version,
                    profile.schema_version,
                    profile.source_signature,
                    profile.supersedes_version,
                    raw,
                    profile.created_at,
                    profile.company_id,
                    profile.profile_version - 1,
                ),
            )
            row = connection.execute(
                "SELECT profile_json FROM company_profile_snapshots WHERE company_id = ? AND profile_version = ?",
                (profile.company_id, profile.profile_version),
            ).fetchone()
            if not row or row["profile_json"] != raw:
                raise ValueError("Company history changed; reload before rebuilding.")

    @staticmethod
    def _from_json(raw: str) -> CompanyProfileSnapshot:
        data = json.loads(raw)
        data["sources"] = tuple(CompanyPublicSource(**item) for item in data.get("sources", ()))
        data["claims"] = tuple(CompanyClaim(**item) for item in data.get("claims", ()))
        for name in (
            "source_refs",
            "products_services",
            "market_context",
            "public_culture_signals",
            "public_strategy_priorities",
            "recent_developments",
            "role_context",
            "uncertainties",
        ):
            data[name] = tuple(
                data.get(name, ())
            )
        return CompanyProfileSnapshot(**data)
