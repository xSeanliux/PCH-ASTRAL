import shutil
from pathlib import Path

import pytest

SAMPLE_DATASET = Path(__file__).parents[1] / "sample_dataset.csv"


@pytest.fixture
def quartet_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real `tmp_path/d.csv`, and quartets written under `tmp_path`.

    Quartet-based runners read the dataset in `execute`, before the stubbed script.
    """
    monkeypatch.setenv("PCH_SCRATCH", str(tmp_path / "scratch"))
    return Path(shutil.copy(SAMPLE_DATASET, tmp_path / "d.csv"))
