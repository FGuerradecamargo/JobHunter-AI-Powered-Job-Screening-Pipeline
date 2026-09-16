"""Offline tests never inherit application database configuration."""
import os
from pathlib import Path
import tempfile

import pytest

# This must happen before test-module imports (database.py loads dotenv).
os.environ["DATABASE_URL"] = ""
_collection_database = tempfile.TemporaryDirectory(prefix="workpilot-tests-")

from services import database

database.DATABASE_FILE = Path(_collection_database.name) / "collection.db"


@pytest.fixture(autouse=True)
def isolated_application_database(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr(database, "DATABASE_FILE", tmp_path / "test.db")

    def forbidden_pool(*args, **kwargs):
        raise RuntimeError("External databases are forbidden in the offline test suite.")

    monkeypatch.setattr(database, "_get_postgres_pool", forbidden_pool)
    initialize = database.initialize_database
    initialize.cache_clear()
    initialize()
    yield
    initialize.cache_clear()
