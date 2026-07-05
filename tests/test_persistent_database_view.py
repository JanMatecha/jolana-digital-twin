from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from jolana_digital_twin.application import initialize_configured_database, import_libre_csv_to_configured_database
from jolana_digital_twin.config import Settings
from jolana_digital_twin.presentation.streamlit_app import _has_glucose_data, _load_persistent_database_frames


SAMPLE_CSV = Path("data/examples/free_style_libre_sample.csv")


class PersistentDatabaseViewTest(unittest.TestCase):
    def test_load_persistent_database_frames_reads_imported_data(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)
            import_libre_csv_to_configured_database(SAMPLE_CSV, settings)

            glucose_frame, insulin_frame, meals_frame = _load_persistent_database_frames(settings)

            self.assertFalse(glucose_frame.empty)
            self.assertIsInstance(insulin_frame, pd.DataFrame)
            self.assertIsInstance(meals_frame, pd.DataFrame)
            self.assertIn("glucose_source", glucose_frame.columns)
            self.assertEqual(glucose_frame["glucose_source"].tolist(), glucose_frame["source"].tolist())

    def test_load_persistent_database_frames_handles_empty_database(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = _temporary_settings(temp_dir)
            initialize_configured_database(settings)

            glucose_frame, insulin_frame, meals_frame = _load_persistent_database_frames(settings)

            self.assertTrue(glucose_frame.empty)
            self.assertTrue(insulin_frame.empty)
            self.assertTrue(meals_frame.empty)
            self.assertIn("glucose_source", glucose_frame.columns)

    def test_has_glucose_data_returns_false_for_empty_frame(self) -> None:
        self.assertFalse(_has_glucose_data(pd.DataFrame()))

    def test_has_glucose_data_returns_false_without_timestamp(self) -> None:
        frame = pd.DataFrame({"glucose_mmol_l": [7.2]})

        self.assertFalse(_has_glucose_data(frame))

    def test_has_glucose_data_returns_false_without_glucose_column(self) -> None:
        frame = pd.DataFrame({"timestamp": [pd.Timestamp("2026-06-22 09:00")]})

        self.assertFalse(_has_glucose_data(frame))

    def test_has_glucose_data_returns_true_for_valid_glucose_frame(self) -> None:
        frame = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-06-22 09:00")],
                "glucose_mmol_l": [7.2],
            }
        )

        self.assertTrue(_has_glucose_data(frame))


def _temporary_settings(temp_dir: str) -> Settings:
    data_dir = Path(temp_dir) / "data"
    return Settings(
        jolana_env="test",
        data_dir=data_dir,
        db_path=data_dir / "db" / "jolana-test.sqlite",
    )


if __name__ == "__main__":
    unittest.main()
