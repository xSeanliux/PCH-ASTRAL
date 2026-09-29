import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

# Columns deliberately not t1..tN in order: a name that is no `t<number>`, and
# `t10` ahead of `t2`, as the simulator writes them once an outgroup is present.
TAXA = ["OUT", "t1", "t10", "t2"]
DATASET = "\n".join(
    [
        "id,feature,weight," + ",".join(TAXA),
        "l0,l0,1.0,1,1,2,2",
        "l1,l1,1.0,1,2,2,1",
        "l2,l2,1.0,2,1,1,1",
    ]
)

# --resolve-poly values, from commandLineNex.R
MP4 = 3
GA = 4


def _nexus(tmp_path: Path, resolve_poly: int) -> str:
    dataset = tmp_path / "data.csv"
    dataset.write_text(DATASET + "\n")
    nexus = tmp_path / "out.nex"
    out = subprocess.run(
        [
            "Rscript",
            "scripts/R/commandLineNex.R",
            "-H",
            "test",
            "-f",
            str(dataset),
            "-o",
            str(nexus),
            "--resolve-poly",
            str(resolve_poly),
            "--morph-weight",
            "1.0",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    return nexus.read_text()


def _block(nexus: str, start: str) -> list[str]:
    """The non-empty lines between the line starting `start` and the next `;`."""
    lines = [line.strip() for line in nexus.splitlines()]
    begin = next(i for i, line in enumerate(lines) if line.startswith(start))
    end = next(i for i in range(begin + 1, len(lines)) if lines[i].startswith(";"))
    return [line for line in lines[begin + 1 : end] if line]


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript not installed")
def test_ga_matrix_rows_are_labelled_by_taxon_name(tmp_path: Path):
    nexus = _nexus(tmp_path, GA)
    assert _block(nexus, "taxlabels") == TAXA
    # GA's matrix is one row per taxon: `<label>\t<states>`.
    assert [row.split()[0] for row in _block(nexus, "matrix")] == TAXA


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript not installed")
def test_mp4_taxlabels_follow_the_columns(tmp_path: Path):
    assert _block(_nexus(tmp_path, MP4), "taxlabels") == TAXA
