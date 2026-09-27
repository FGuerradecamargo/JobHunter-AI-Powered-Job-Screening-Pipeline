"""Explicit additive migration; does not assign authority to legacy jobs."""
from services.database import get_connection, create_job_observation_schema


def main():
    with get_connection() as connection:
        create_job_observation_schema(connection)


if __name__ == "__main__":
    main()
