from __future__ import annotations

from pathlib import Path

import pandas as pd

from jolana_digital_twin.domain import ImportedData, Meal


class ManualMealsCsvReader:
    source = "manual_meals_csv"

    def read(self, path: str | Path) -> ImportedData:
        frame = pd.read_csv(Path(path), encoding="utf-8-sig")
        required = ["timestamp", "carbs_g"]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(f"Manual meals CSV is missing required columns: {', '.join(missing)}")

        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        for column in ["carbs_g", "fat_g", "protein_g"]:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")

        meals: list[Meal] = []
        for index, row in frame.iterrows():
            timestamp = row.get("timestamp")
            if pd.isna(timestamp):
                continue

            meals.append(
                Meal(
                    timestamp=timestamp.to_pydatetime(),
                    carbs_g=_optional_float(row.get("carbs_g")),
                    fat_g=_optional_float(row.get("fat_g")),
                    protein_g=_optional_float(row.get("protein_g")),
                    source=self.source,
                    note=_optional_str(row.get("note")),
                    source_record_id=str(index),
                )
            )

        return ImportedData(meals=meals)


def _optional_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _optional_str(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None
