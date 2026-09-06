from __future__ import annotations

from dataclasses import asdict
import json
from uuid import uuid4

from models.app_user import AppUser
from models.candidate import Candidate
from services.database import (
    create_account_security_schema,
    create_user_identity_schema,
    get_connection,
    utc_now,
)
from services.google_identity_service import (
    GoogleIdentityResolution,
    GoogleIdentityService,
)
from services.user_identity_repository import (
    UserIdentityRepository,
)
class GoogleAccountService:
    def __init__(self) -> None:
        self.identity_repository = (
            UserIdentityRepository()
        )

    def link_existing_account(
        self,
        *,
        resolution: GoogleIdentityResolution,
        authenticated_user: AppUser,
    ) -> AppUser:
        if (
            resolution.status
            != GoogleIdentityService
            .LINK_REQUIRED
        ):
            raise ValueError(
                "Google identity is not eligible "
                "for account linking."
            )

        if resolution.user is None:
            raise ValueError(
                "Existing WorkPilot account "
                "is required for linking."
            )

        if (
            authenticated_user.id
            != resolution.user.id
        ):
            raise ValueError(
                "Authenticated WorkPilot account "
                "does not match the Google identity."
            )

        self.identity_repository.link(
            user_id=authenticated_user.id,
            provider=GoogleIdentityService.PROVIDER,
            subject=resolution.subject,
            provider_email=resolution.email,
        )

        return authenticated_user

    def register(
        self,
        resolution: GoogleIdentityResolution,
    ) -> AppUser:
        if (
            resolution.status
            != GoogleIdentityService
            .REGISTRATION_REQUIRED
        ):
            raise ValueError(
                "Google identity is not eligible "
                "for registration."
            )

        user_id = uuid4().hex
        candidate_id = (
            f"candidate_{uuid4().hex}"
        )

        candidate = Candidate(
            id=candidate_id,
            name=resolution.display_name,
            current_role="",
            current_level="",
            professional_summary="",
        )

        now = utc_now()

        with get_connection() as connection:
            create_account_security_schema(
                connection
            )
            create_user_identity_schema(
                connection
            )

            connection.execute(
                """
                INSERT INTO candidates (
                    id,
                    name,
                    "current_role",
                    current_level,
                    professional_summary,
                    target_roles_json,
                    spoken_languages_json,
                    skills_json,
                    strengths_json,
                    development_areas_json,
                    professional_experiences_json,
                    proven_capabilities_json,
                    transferable_capabilities_json,
                    developing_capabilities_json,
                    technical_tools_json,
                    domain_experience_json,
                    competitive_role_families_json,
                    bridge_role_families_json,
                    target_role_families_json,
                    preferences_json,
                    constraints_json,
                    priorities_json,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    candidate.id,
                    candidate.name,
                    candidate.current_role,
                    candidate.current_level,
                    candidate.professional_summary,
                    json.dumps(
                        candidate.target_roles
                    ),
                    json.dumps(
                        candidate.spoken_languages
                    ),
                    json.dumps(
                        candidate.skills
                    ),
                    json.dumps(
                        candidate.strengths
                    ),
                    json.dumps(
                        candidate.development_areas
                    ),
                    json.dumps([]),
                    json.dumps(
                        candidate.proven_capabilities
                    ),
                    json.dumps(
                        candidate.transferable_capabilities
                    ),
                    json.dumps(
                        candidate.developing_capabilities
                    ),
                    json.dumps(
                        candidate.technical_tools
                    ),
                    json.dumps(
                        candidate.domain_experience
                    ),
                    json.dumps(
                        candidate.competitive_role_families
                    ),
                    json.dumps(
                        candidate.bridge_role_families
                    ),
                    json.dumps(
                        candidate.target_role_families
                    ),
                    json.dumps(
                        asdict(
                            candidate.preferences
                        )
                    ),
                    json.dumps(
                        asdict(
                            candidate.constraints
                        )
                    ),
                    json.dumps([]),
                    now,
                    now,
                ),
            )

            connection.execute(
                """
                INSERT INTO users (
                    id,
                    email,
                    display_name,
                    candidate_id,
                    access_level,
                    password_hash,
                    email_verified_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    resolution.email,
                    resolution.display_name,
                    candidate_id,
                    "user",
                    None,
                    now,
                    now,
                    now,
                ),
            )

            connection.execute(
                """
                INSERT INTO user_identities (
                    id,
                    user_id,
                    provider,
                    subject,
                    provider_email,
                    created_at,
                    updated_at,
                    last_authenticated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    user_id,
                    GoogleIdentityService.PROVIDER,
                    resolution.subject,
                    resolution.email,
                    now,
                    now,
                    now,
                ),
            )

        return AppUser(
            id=user_id,
            email=resolution.email,
            display_name=resolution.display_name,
            candidate_id=candidate_id,
            access_level="user",
        )
