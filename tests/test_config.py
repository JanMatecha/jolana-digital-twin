from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from jolana_digital_twin.config import DATA_SUBDIRECTORIES, ensure_data_directories, get_settings


class ConfigTest(unittest.TestCase):
    def test_default_dev_settings_use_data_dev(self) -> None:
        settings = get_settings({})

        self.assertEqual(settings.jolana_env, "dev")
        self.assertEqual(settings.data_dir, Path("data-dev"))
        self.assertEqual(settings.db_path, Path("data-dev/db/jolana-dev.sqlite"))

    def test_environment_overrides_data_dir_and_db_path(self) -> None:
        settings = get_settings(
            {
                "JOLANA_ENV": "test",
                "JOLANA_DATA_DIR": "custom-data",
                "JOLANA_DB_PATH": "custom-data/db/custom.sqlite",
            }
        )

        self.assertEqual(settings.jolana_env, "test")
        self.assertEqual(settings.data_dir, Path("custom-data"))
        self.assertEqual(settings.db_path, Path("custom-data/db/custom.sqlite"))

    def test_db_path_defaults_under_overridden_data_dir(self) -> None:
        settings = get_settings({"JOLANA_DATA_DIR": "custom-data"})

        self.assertEqual(settings.data_dir, Path("custom-data"))
        self.assertEqual(settings.db_path, Path("custom-data/db/jolana-dev.sqlite"))

    def test_ensure_data_directories_creates_configured_tree(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "jolana-data"
            settings = get_settings(
                {
                    "JOLANA_ENV": "test",
                    "JOLANA_DATA_DIR": str(data_dir),
                    "JOLANA_DB_PATH": str(data_dir / "db" / "test.sqlite"),
                }
            )

            ensure_data_directories(settings)

            self.assertTrue(data_dir.is_dir())
            for name in DATA_SUBDIRECTORIES:
                self.assertTrue((data_dir / name).is_dir())


if __name__ == "__main__":
    unittest.main()
