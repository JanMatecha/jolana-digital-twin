from __future__ import annotations

from pathlib import Path

from jolana_digital_twin.readers import LibreCsvReader, ManualMealsCsvReader
from jolana_digital_twin.storage import SQLiteStore


def import_libre_csv(csv_path: str | Path, db_path: str | Path) -> int:
    csv_path = Path(csv_path)
    reader = LibreCsvReader()
    imported_data = reader.read(csv_path)
    store = SQLiteStore(db_path)
    return store.save_import(imported_data, source=reader.source, file_path=csv_path)


def import_manual_meals_csv(csv_path: str | Path, db_path: str | Path) -> int:
    csv_path = Path(csv_path)
    reader = ManualMealsCsvReader()
    imported_data = reader.read(csv_path)
    store = SQLiteStore(db_path)
    return store.save_import(imported_data, source=reader.source, file_path=csv_path)
