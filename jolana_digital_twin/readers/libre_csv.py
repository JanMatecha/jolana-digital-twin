from __future__ import annotations

from pathlib import Path

import pandas as pd

from jolana_digital_twin.domain import GlucoseReading, ImportedData, InsulinDose, Meal
from jolana_digital_twin.libre import (
    CARBS_COLUMN,
    FAT_COLUMN,
    LONG_INSULIN_COLUMN,
    RAPID_INSULIN_COLUMN,
    load_libre_csv,
)


DEVICE_COLUMN = "Sériové číslo"


class LibreCsvReader:
    source = "libre_csv"

    def read(self, path: str | Path) -> ImportedData:
        frame = load_libre_csv(path)

        glucose_readings: list[GlucoseReading] = []
        insulin_doses: list[InsulinDose] = []
        meals: list[Meal] = []

        for index, row in frame.iterrows():
            timestamp = row.get("timestamp")
            if pd.isna(timestamp):
                continue

            source_device = _optional_str(row.get(DEVICE_COLUMN))
            source_record_id = str(index)
            timestamp_value = timestamp.to_pydatetime()

            glucose = row.get("glucose_mmol_l")
            if pd.notna(glucose):
                glucose_readings.append(
                    GlucoseReading(
                        timestamp=timestamp_value,
                        glucose_mmol_l=float(glucose),
                        source=f"{self.source}:{row.get('glucose_source', 'unknown')}",
                        source_device=source_device,
                        source_record_id=source_record_id,
                    )
                )

            rapid_units = row.get(RAPID_INSULIN_COLUMN)
            if pd.notna(rapid_units):
                insulin_doses.append(
                    InsulinDose(
                        timestamp=timestamp_value,
                        insulin_type="rapid",
                        units=float(rapid_units),
                        source=self.source,
                        source_device=source_device,
                        source_record_id=source_record_id,
                    )
                )

            long_units = row.get(LONG_INSULIN_COLUMN)
            if pd.notna(long_units):
                insulin_doses.append(
                    InsulinDose(
                        timestamp=timestamp_value,
                        insulin_type="long",
                        units=float(long_units),
                        source=self.source,
                        source_device=source_device,
                        source_record_id=source_record_id,
                    )
                )

            carbs_g = row.get(CARBS_COLUMN)
            fat_g = row.get(FAT_COLUMN)
            if pd.notna(carbs_g) or pd.notna(fat_g):
                meals.append(
                    Meal(
                        timestamp=timestamp_value,
                        carbs_g=float(carbs_g) if pd.notna(carbs_g) else None,
                        fat_g=float(fat_g) if pd.notna(fat_g) else None,
                        source=self.source,
                        source_device=source_device,
                        source_record_id=source_record_id,
                    )
                )

        return ImportedData(
            glucose_readings=glucose_readings,
            insulin_doses=insulin_doses,
            meals=meals,
        )


def _optional_str(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None
