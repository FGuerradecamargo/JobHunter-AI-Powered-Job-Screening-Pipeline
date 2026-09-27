"""Immutable global history. No initialization/migration on request paths."""
from dataclasses import asdict
import hashlib
import json

from models.market_profile import MarketConfidence, MarketPattern, MarketProfile, MarketSegment
from services.database import get_connection


def _segment_key(segment):
    return hashlib.sha256(json.dumps(asdict(segment), sort_keys=True).encode()).hexdigest()


def _decode(raw):
    value = json.loads(raw)
    value["segment"] = MarketSegment(**value["segment"])
    value["patterns"] = tuple(MarketPattern(**{**item,
        "source_job_ids": tuple(item["source_job_ids"]),
        "confidence": MarketConfidence(item["confidence"])}) for item in value["patterns"])
    value["uncertainties"] = tuple(value.get("uncertainties", ()))
    return MarketProfile(**value)


class MarketProfileRepository:
    def current(self, segment):
        with get_connection() as connection:
            row = connection.execute(
                "SELECT profile_json FROM market_profile_snapshots WHERE segment_key = ? "
                "ORDER BY profile_version DESC LIMIT 1", (_segment_key(segment),),
            ).fetchone()
        return _decode(row["profile_json"]) if row else None

    def list_current(self):
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT current.profile_json
                FROM market_profile_snapshots current
                JOIN (
                    SELECT segment_key, MAX(profile_version) AS profile_version
                    FROM market_profile_snapshots
                    GROUP BY segment_key
                ) latest
                  ON latest.segment_key = current.segment_key
                 AND latest.profile_version = current.profile_version
                ORDER BY current.segment_key
                """
            ).fetchall()
        return tuple(_decode(row["profile_json"]) for row in rows)

    def version(self, segment, version):
        with get_connection() as connection:
            row = connection.execute(
                "SELECT profile_json FROM market_profile_snapshots "
                "WHERE segment_key = ? AND profile_version = ?", (_segment_key(segment), version),
            ).fetchone()
        return _decode(row["profile_json"]) if row else None

    def save(self, profile):
        key = _segment_key(profile.segment)
        raw = json.dumps(asdict(profile), sort_keys=True)
        # PK plus predecessor condition prevents competing writers overwriting history.
        with get_connection() as connection:
            connection.execute(
                """INSERT INTO market_profile_snapshots
                   (segment_key, profile_version, profile_json, created_at)
                   SELECT ?, ?, ?, ? WHERE
                   COALESCE((SELECT MAX(profile_version) FROM market_profile_snapshots
                             WHERE segment_key = ?), 0) = ?
                   ON CONFLICT (segment_key, profile_version) DO NOTHING""",
                (key, profile.profile_version, raw, profile.created_at, key, profile.profile_version - 1),
            )
            row = connection.execute(
                "SELECT profile_json FROM market_profile_snapshots "
                "WHERE segment_key = ? AND profile_version = ?", (key, profile.profile_version),
            ).fetchone()
            if not row or row["profile_json"] != raw:
                raise ValueError("Market history changed; reload before rebuilding.")
