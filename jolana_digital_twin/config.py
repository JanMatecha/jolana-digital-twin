from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


DEFAULT_ENV = "dev"
DEFAULT_DATA_DIR = Path("data-dev")
DATA_SUBDIRECTORIES = (
    "db",
    "raw",
    "processed",
    "manual",
    "attachments",
    "derived",
    "exports",
    "backups",
)


@dataclass(frozen=True)
class Settings:
    jolana_env: str
    data_dir: Path
    db_path: Path


def get_settings(environ: Mapping[str, str] | None = None) -> Settings:
    source = environ if environ is not None else os.environ
    jolana_env = source.get("JOLANA_ENV", DEFAULT_ENV)
    data_dir = Path(source.get("JOLANA_DATA_DIR", str(DEFAULT_DATA_DIR)))
    db_path = Path(source.get("JOLANA_DB_PATH", str(data_dir / "db" / "jolana-dev.sqlite")))
    return Settings(jolana_env=jolana_env, data_dir=data_dir, db_path=db_path)


def ensure_data_directories(settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    resolved.data_dir.mkdir(parents=True, exist_ok=True)
    for name in DATA_SUBDIRECTORIES:
        (resolved.data_dir / name).mkdir(parents=True, exist_ok=True)


_SETTINGS = get_settings()
JOLANA_ENV = _SETTINGS.jolana_env
JOLANA_DATA_DIR = _SETTINGS.data_dir
JOLANA_DB_PATH = _SETTINGS.db_path
