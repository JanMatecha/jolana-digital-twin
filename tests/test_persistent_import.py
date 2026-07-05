from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from jolana_digital_twin.application import import_libre_csv_to_configured_database
from jolana_digital_twin.config import Settings
from jolana_digital_twin.storage import SQLiteStore


SAMPLE_CSV = Path("data/examples/free_style_libre_sample.csv")


class PersistentLibreImportTest(unittest.TestCase):
    def test_import_creates_raw_copy_and_persistent_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)

            result = import_libre_csv_to_configured_database(SAMPLE_CSV, settings)

            self.assertEqual(result.status, "imported")
            self.assertIsNotNone(result.import_id)
            self.assertIsNotNone(result.raw_path)
            self.assertTrue(result.raw_path.is_file())
            self.assertTrue(_is_relative_to(result.raw_path, settings.data_dir / "raw" / "libre"))
            self.assertTrue(settings.db_path.is_file())
            self.assertEqual(_count_rows(settings.db_path, "imports"), 1)
            self.assertGreater(_count_rows(settings.db_path, "glucose_readings"), 0)

    def test_duplicate_import_does_not_insert_rows_twice(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)

            first = import_libre_csv_to_configured_database(SAMPLE_CSV, settings)
            glucose_count = _count_rows(settings.db_path, "glucose_readings")
            second = import_libre_csv_to_configured_database(SAMPLE_CSV, settings)

            self.assertEqual(first.status, "imported")
            self.assertEqual(second.status, "duplicate")
            self.assertEqual(_count_rows(settings.db_path, "imports"), 1)
            self.assertEqual(_count_rows(settings.db_path, "glucose_readings"), glucose_count)

    def test_original_file_name_cannot_escape_raw_libre_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)

            result = import_libre_csv_to_configured_database(
                SAMPLE_CSV,
                settings,
                original_file_name="../evil.csv",
            )

            raw_dir = settings.data_dir / "raw" / "libre"
            self.assertIsNotNone(result.raw_path)
            self.assertTrue(_is_relative_to(result.raw_path, raw_dir))
            self.assertFalse((settings.data_dir / "raw" / "evil.csv").exists())
            self.assertFalse((settings.data_dir / "evil.csv").exists())

    def test_import_result_contains_counts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)

            result = import_libre_csv_to_configured_database(SAMPLE_CSV, settings)

            self.assertGreater(result.glucose_readings, 0)
            self.assertGreaterEqual(result.insulin_doses, 0)
            self.assertGreaterEqual(result.meals, 0)

    def test_sqlite_store_finds_import_id_for_checksum(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)
            result = import_libre_csv_to_configured_database(SAMPLE_CSV, settings)
            store = SQLiteStore(settings.db_path)

            self.assertEqual(store.import_id_for_checksum("libre_csv", result.checksum), result.import_id)
            self.assertTrue(store.has_import_checksum("libre_csv", result.checksum))


def _temporary_settings(temp_dir: str) -> Settings:
    data_dir = Path(temp_dir) / "data"
    return Settings(
        jolana_env="test",
        data_dir=data_dir,
        db_path=data_dir / "db" / "jolana.sqlite",
    )


def _count_rows(db_path: Path, table: str) -> int:
    with closing(sqlite3.connect(db_path)) as connection:
        return int(connection.execute(f"select count(*) from {table}").fetchone()[0])


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    unittest.main()
