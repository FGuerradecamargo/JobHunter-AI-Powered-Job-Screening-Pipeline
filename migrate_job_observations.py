"""Explicit additive migration. Does not classify or rewrite existing job data."""
from services.database import get_connection, is_postgres
from services.job_observation_schema import migrate_job_observations


def migrate():
    with get_connection() as connection:
        migrate_job_observations(connection, postgres=is_postgres())


if __name__ == "__main__":
    migrate()
    print("Job observation schema is ready; legacy job content was not changed.")
