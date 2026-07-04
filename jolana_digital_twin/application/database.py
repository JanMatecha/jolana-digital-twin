from __future__ import annotations

from pathlib import Path

from jolana_digital_twin.config import Settings, ensure_data_directories, get_settings
from jolana_digital_twin.storage import SQLiteStore


def initialize_configured_database(settings: Settings | None = None) -> Path:
    resolved = settings or get_settings()
    ensure_data_directories(resolved)
    resolved.db_path.parent.mkdir(parents=True, exist_ok=True)
    SQLiteStore(resolved.db_path).initialize()
    return resolved.db_path
