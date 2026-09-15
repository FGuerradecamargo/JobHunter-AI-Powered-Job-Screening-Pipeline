"""Global market and employer scheduling only; Gmail retains its separate entry point."""
import json


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from services.database import initialize_database
        from services.source_schedule_service import SourceScheduleService
        from services.job_archive_service import JobArchiveService
        initialize_database()
        runs = SourceScheduleService().run()
        archived = JobArchiveService().archive_stale_global_jobs()
        print(json.dumps({"status": "completed", "sources": runs, "archived": archived}))
        return 0
    except Exception:
        print(json.dumps({"status": "failed", "error_code": "scheduler_system_failure"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
