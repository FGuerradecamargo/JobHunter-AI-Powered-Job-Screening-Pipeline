from services.database import initialize_database


def migrate() -> None:
    # Initialization now upgrades global provenance on both supported databases.
    initialize_database()


def main() -> None:
    migrate()
    print("Global job ingestion schema is ready.")


if __name__ == "__main__":
    main()
