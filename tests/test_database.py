from pathlib import Path
from contextlib import closing
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from jolana_digital_twin.application import initialize_configured_database
from jolana_digital_twin.config import Settings
from jolana_digital_twin.storage import SQLiteStore


class ConfiguredDatabaseTest(unittest.TestCase):
    def test_initialize_configured_database_creates_sqlite_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)

            db_path = initialize_configured_database(settings)

            self.assertEqual(db_path, settings.db_path)
            self.assertTrue(settings.db_path.is_file())

    def test_initialize_configured_database_creates_parent_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir, db_relative_path=Path("nested/db/jolana.sqlite"))

            initialize_configured_database(settings)

            self.assertTrue(settings.db_path.parent.is_dir())
            self.assertTrue(settings.db_path.is_file())

    def test_initialize_configured_database_is_repeatable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)

            initialize_configured_database(settings)
            initialize_configured_database(settings)

            self.assertEqual(SQLiteStore(settings.db_path).applied_schema_versions(), [1])

    def test_initialize_configured_database_preserves_existing_database_content(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)
            settings.db_path.parent.mkdir(parents=True)
            with closing(sqlite3.connect(settings.db_path)) as connection:
                connection.execute("create table existing_data (value text not null)")
                connection.execute("insert into existing_data (value) values ('keep me')")
                connection.commit()

            initialize_configured_database(settings)

            with closing(sqlite3.connect(settings.db_path)) as connection:
                value = connection.execute("select value from existing_data").fetchone()[0]
            self.assertEqual(value, "keep me")

    def test_sqlite_store_reports_schema_version_one(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)

            initialize_configured_database(settings)

            self.assertEqual(SQLiteStore(settings.db_path).schema_version(), 1)

    def test_initialize_configured_database_creates_expected_tables(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)

            initialize_configured_database(settings)

            self.assertEqual(
                _table_names(settings.db_path),
                {
                    "glucose_readings",
                    "imports",
                    "insulin_doses",
                    "meals",
                    "schema_migrations",
                    "sqlite_sequence",
                },
            )


def _temporary_settings(temp_dir: str, db_relative_path: Path = Path("data/db/jolana.sqlite")) -> Settings:
    data_dir = Path(temp_dir) / "data"
    return Settings(
        jolana_env="test",
        data_dir=data_dir,
        db_path=Path(temp_dir) / db_relative_path,
    )


def _table_names(db_path: Path) -> set[str]:
    with closing(sqlite3.connect(db_path)) as connection:
        rows = connection.execute(
            """
            select name
            from sqlite_master
            where type = 'table'
            """
        ).fetchall()
    return {str(row[0]) for row in rows}


if __name__ == "__main__":
    unittest.main()
