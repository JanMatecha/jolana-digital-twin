from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
import unittest

from jolana_digital_twin.application import import_libre_csv
from jolana_digital_twin.readers import LibreCsvReader, ManualMealsCsvReader
from jolana_digital_twin.storage import SQLiteStore


SAMPLE_CSV = Path("data/examples/free_style_libre_sample.csv")


class ImportPipelineTest(unittest.TestCase):
    def test_libre_reader_returns_universal_domain_data(self) -> None:
        imported_data = LibreCsvReader().read(SAMPLE_CSV)

        self.assertEqual(len(imported_data.glucose_readings), 288)
        self.assertEqual(len(imported_data.insulin_doses), 12)
        self.assertEqual(len(imported_data.meals), 9)
        self.assertEqual(imported_data.insulin_doses[0].insulin_type, "rapid")
        self.assertEqual(imported_data.meals[0].carbs_g, 42.0)
        self.assertEqual(imported_data.meals[0].fat_g, 12.0)

    def test_imports_libre_csv_to_sqlite(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite"

            import_id = import_libre_csv(SAMPLE_CSV, db_path)
            store = SQLiteStore(db_path)

            self.assertEqual(import_id, 1)
            self.assertEqual(len(store.glucose_readings_frame()), 288)
            self.assertEqual(len(store.insulin_doses_frame()), 12)
            self.assertEqual(len(store.meals_frame()), 9)

    def test_manual_meals_reader_loads_carbs_and_fat(self) -> None:
        with NamedTemporaryFile("w", encoding="utf-8", suffix=".csv", delete=False) as file:
            file.write("timestamp,carbs_g,fat_g,protein_g,note\n")
            file.write("2026-06-26 11:47,11.5,7.0,,obed\n")
            path = Path(file.name)

        imported_data = ManualMealsCsvReader().read(path)

        self.assertEqual(len(imported_data.meals), 1)
        self.assertEqual(imported_data.meals[0].carbs_g, 11.5)
        self.assertEqual(imported_data.meals[0].fat_g, 7.0)
        self.assertEqual(imported_data.meals[0].note, "obed")


if __name__ == "__main__":
    unittest.main()
