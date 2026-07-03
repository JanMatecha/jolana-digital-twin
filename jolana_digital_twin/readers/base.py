from __future__ import annotations

from pathlib import Path
from typing import Protocol

from jolana_digital_twin.domain import ImportedData


class DataReader(Protocol):
    def read(self, path: str | Path) -> ImportedData:
        """Read source data and return the universal domain format."""
