from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


TIMESTAMP_COLUMN = "Časová značka zařízení"
HISTORIC_GLUCOSE_COLUMN = "Historie údajů o glukóze mmol/L"
SCAN_GLUCOSE_COLUMN = "Skenovat glukózu mmol/L"
RAPID_INSULIN_COLUMN = "Inzulín s rychlým účinkem (jednotky)"
LONG_INSULIN_COLUMN = "Inzulín s dlouhým účinkem (jednotky)"
CARBS_COLUMN = "Karbohydráty (gramy)"
FAT_COLUMN = "Tuky (gramy)"


@dataclass(frozen=True)
class LibreSummary:
    rows: int
    glucose_points: int
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    mean_glucose: float | None
    min_glucose: float | None
    max_glucose: float | None


def load_libre_csv(path: str | Path) -> pd.DataFrame:
    """Load a FreeStyle Libre CSV export into a normalized dataframe."""
    path = Path(path)
    frame = pd.read_csv(path, skiprows=1, encoding="utf-8-sig")

    required = [TIMESTAMP_COLUMN, HISTORIC_GLUCOSE_COLUMN, SCAN_GLUCOSE_COLUMN]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Libre CSV is missing required columns: {', '.join(missing)}")

    frame["timestamp"] = pd.to_datetime(
        frame[TIMESTAMP_COLUMN],
        format="%d-%m-%Y %H:%M",
        errors="coerce",
    )

    for column in [
        HISTORIC_GLUCOSE_COLUMN,
        SCAN_GLUCOSE_COLUMN,
        RAPID_INSULIN_COLUMN,
        LONG_INSULIN_COLUMN,
        CARBS_COLUMN,
        FAT_COLUMN,
    ]:
        if column in frame.columns:
            frame[column] = _to_float(frame[column])

    frame["glucose_mmol_l"] = frame[HISTORIC_GLUCOSE_COLUMN].combine_first(
        frame[SCAN_GLUCOSE_COLUMN]
    )
    frame["glucose_source"] = "historic"
    frame.loc[frame[HISTORIC_GLUCOSE_COLUMN].isna() & frame[SCAN_GLUCOSE_COLUMN].notna(), "glucose_source"] = "scan"

    normalized = frame.sort_values("timestamp").reset_index(drop=True)
    return normalized


def summarize(frame: pd.DataFrame) -> LibreSummary:
    glucose = frame["glucose_mmol_l"].dropna()
    timestamps = frame.loc[frame["timestamp"].notna(), "timestamp"]

    return LibreSummary(
        rows=len(frame),
        glucose_points=len(glucose),
        start=timestamps.min() if not timestamps.empty else None,
        end=timestamps.max() if not timestamps.empty else None,
        mean_glucose=round(float(glucose.mean()), 2) if not glucose.empty else None,
        min_glucose=round(float(glucose.min()), 2) if not glucose.empty else None,
        max_glucose=round(float(glucose.max()), 2) if not glucose.empty else None,
    )


def _to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype("string").str.replace(",", ".", regex=False),
        errors="coerce",
    )
