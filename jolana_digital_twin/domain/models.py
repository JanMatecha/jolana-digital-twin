from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class GlucoseReading:
    timestamp: datetime
    glucose_mmol_l: float
    source: str
    source_device: str | None = None
    source_record_id: str | None = None


@dataclass(frozen=True)
class InsulinDose:
    timestamp: datetime
    insulin_type: str
    units: float
    source: str
    note: str | None = None
    source_device: str | None = None
    source_record_id: str | None = None


@dataclass(frozen=True)
class Meal:
    timestamp: datetime
    carbs_g: float | None
    fat_g: float | None = None
    protein_g: float | None = None
    source: str = "manual"
    note: str | None = None
    source_device: str | None = None
    source_record_id: str | None = None


@dataclass(frozen=True)
class ImportedData:
    glucose_readings: list[GlucoseReading] = field(default_factory=list)
    insulin_doses: list[InsulinDose] = field(default_factory=list)
    meals: list[Meal] = field(default_factory=list)
