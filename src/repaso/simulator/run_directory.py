"""The rule that a simulated run never writes into the state another run left behind."""

from pathlib import Path

MUST_BE_EMPTY = "data-dir must be empty; choose a new directory to preserve previous runs"


def occupied(data_dir: Path) -> bool:
    return data_dir.exists() and any(data_dir.iterdir())
