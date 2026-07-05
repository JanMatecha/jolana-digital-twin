from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import shutil

from jolana_digital_twin.config import Settings, ensure_data_directories, get_settings
from jolana_digital_twin.readers import LibreCsvReader
from jolana_digital_twin.storage import SQLiteStore


@dataclass(frozen=True)
class PersistentImportResult:
    status: str
    import_id: int | None
    checksum: str
    raw_path: Path | None
    glucose_readings: int
    insulin_doses: int
    meals: int
    message: str


def import_libre_csv_to_configured_database(
    csv_path: str | Path,
    settings: Settings | None = None,
    original_file_name: str | None = None,
) -> PersistentImportResult:
    resolved = settings or get_settings()
    ensure_data_directories(resolved)
    raw_dir = resolved.data_dir / "raw" / "libre"
    raw_dir.mkdir(parents=True, exist_ok=True)

    source_path = Path(csv_path)
    checksum = _sha256(source_path)
    reader = LibreCsvReader()
    store = SQLiteStore(resolved.db_path)

    existing_import_id = store.import_id_for_checksum(reader.source, checksum)
    if existing_import_id is not None:
        return PersistentImportResult(
            status="duplicate",
            import_id=existing_import_id,
            checksum=checksum,
            raw_path=None,
            glucose_readings=0,
            insulin_doses=0,
            meals=0,
            message="Tento CSV soubor uz byl importovan.",
        )

    raw_path = _copy_raw_file(source_path, raw_dir, checksum, original_file_name)
    imported_data = reader.read(raw_path)
    import_id = store.save_import(imported_data, source=reader.source, file_path=raw_path)

    return PersistentImportResult(
        status="imported",
        import_id=import_id,
        checksum=checksum,
        raw_path=raw_path,
        glucose_readings=len(imported_data.glucose_readings),
        insulin_doses=len(imported_data.insulin_doses),
        meals=len(imported_data.meals),
        message="CSV soubor byl importovan do persistentni databaze.",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_raw_file(source_path: Path, raw_dir: Path, checksum: str, original_file_name: str | None) -> Path:
    safe_name = _safe_file_name(original_file_name or source_path.name)
    target = _unique_raw_path(raw_dir, f"{checksum[:12]}_{safe_name}")
    shutil.copy2(source_path, target)
    return target


def _safe_file_name(file_name: str) -> str:
    name = Path(file_name).name.strip() or "libre.csv"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return safe or "libre.csv"


def _unique_raw_path(raw_dir: Path, file_name: str) -> Path:
    candidate = raw_dir / file_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        candidate = raw_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
