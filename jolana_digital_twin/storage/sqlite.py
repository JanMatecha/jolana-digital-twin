from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from jolana_digital_twin.domain import ImportedData


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.parent != Path("."):
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                create table if not exists imports (
                    id integer primary key autoincrement,
                    source text not null,
                    file_name text,
                    imported_at text not null,
                    checksum text
                );

                create table if not exists glucose_readings (
                    id integer primary key autoincrement,
                    timestamp text not null,
                    glucose_mmol_l real not null,
                    source text not null,
                    source_device text,
                    source_record_id text,
                    import_id integer references imports(id)
                );

                create table if not exists insulin_doses (
                    id integer primary key autoincrement,
                    timestamp text not null,
                    insulin_type text not null,
                    units real not null,
                    source text not null,
                    note text,
                    source_device text,
                    source_record_id text,
                    import_id integer references imports(id)
                );

                create table if not exists meals (
                    id integer primary key autoincrement,
                    timestamp text not null,
                    carbs_g real,
                    fat_g real,
                    protein_g real,
                    source text not null,
                    note text,
                    source_device text,
                    source_record_id text,
                    import_id integer references imports(id)
                );
                """
            )

    def save_import(
        self,
        imported_data: ImportedData,
        source: str,
        file_path: str | Path | None = None,
    ) -> int:
        self.initialize()
        file_path = Path(file_path) if file_path is not None else None

        with self._connect() as connection:
            cursor = connection.execute(
                """
                insert into imports (source, file_name, imported_at, checksum)
                values (?, ?, ?, ?)
                """,
                (
                    source,
                    file_path.name if file_path else None,
                    datetime.utcnow().isoformat(timespec="seconds"),
                    _checksum(file_path) if file_path else None,
                ),
            )
            import_id = int(cursor.lastrowid)

            connection.executemany(
                """
                insert into glucose_readings (
                    timestamp, glucose_mmol_l, source, source_device, source_record_id, import_id
                ) values (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        reading.timestamp.isoformat(timespec="minutes"),
                        reading.glucose_mmol_l,
                        reading.source,
                        reading.source_device,
                        reading.source_record_id,
                        import_id,
                    )
                    for reading in imported_data.glucose_readings
                ],
            )
            connection.executemany(
                """
                insert into insulin_doses (
                    timestamp, insulin_type, units, source, note, source_device, source_record_id, import_id
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        dose.timestamp.isoformat(timespec="minutes"),
                        dose.insulin_type,
                        dose.units,
                        dose.source,
                        dose.note,
                        dose.source_device,
                        dose.source_record_id,
                        import_id,
                    )
                    for dose in imported_data.insulin_doses
                ],
            )
            connection.executemany(
                """
                insert into meals (
                    timestamp, carbs_g, fat_g, protein_g, source, note, source_device, source_record_id, import_id
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        meal.timestamp.isoformat(timespec="minutes"),
                        meal.carbs_g,
                        meal.fat_g,
                        meal.protein_g,
                        meal.source,
                        meal.note,
                        meal.source_device,
                        meal.source_record_id,
                        import_id,
                    )
                    for meal in imported_data.meals
                ],
            )

        return import_id

    def glucose_readings_frame(self) -> pd.DataFrame:
        return self._read_frame(
            """
            select timestamp, glucose_mmol_l, source, source_device, source_record_id
            from glucose_readings
            order by timestamp
            """
        )

    def insulin_doses_frame(self) -> pd.DataFrame:
        return self._read_frame(
            """
            select timestamp, insulin_type, units, source, note, source_device, source_record_id
            from insulin_doses
            order by timestamp
            """
        )

    def meals_frame(self) -> pd.DataFrame:
        return self._read_frame(
            """
            select timestamp, carbs_g, fat_g, protein_g, source, note, source_device, source_record_id
            from meals
            order by timestamp
            """
        )

    def _read_frame(self, query: str) -> pd.DataFrame:
        self.initialize()
        with self._connect() as connection:
            frame = pd.read_sql_query(query, connection)
        if "timestamp" in frame.columns:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        return frame

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _checksum(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
