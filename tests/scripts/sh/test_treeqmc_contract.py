import subprocess
from pathlib import Path

import pytest

from scripts.lib.pch import PCH_W
from scripts.lib.types import Dataset

ROOT = Path(__file__).resolve().parents[3]
TQMC = ROOT / "bin" / "TREE-QMC" / "tree-qmc"
DS = (
    ROOT
    / "experiments/sample_experiment/simulation_data/simulated_data"
    / "high_0.0_4_320/sim_0_10_1.csv"
)


@pytest.mark.skipif(
    not (TQMC.exists() and DS.exists()),
    reason="tree-qmc binary or sample dataset not available",
)
def test_treeqmc_accepts_pch_quartets(tmp_path):
    # Two things at once:
    # 1) regression — real datasets carry float weights ("50.0"); Dataset.from_path
    #    must parse them (int(float(...))).
    # 2) contract — tree-qmc --quartets accepts PCH-W quartets as
    #    "((A,B),(C,D));weight" and emits a species tree.
    dataset = Dataset.from_path(DS)
    quartets = PCH_W.get_quartets(dataset)
    assert quartets, "expected quartets from the real dataset"

    qfile = tmp_path / "quartets.txt"
    qfile.write_text("".join(f"{q};{w}\n" for q, w in quartets.items()))
    out = tmp_path / "tree.nwk"

    proc = subprocess.run(
        [str(TQMC), "--quartets", "-i", str(qfile), "-o", str(out), "--norm_atax", "2"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    tree = out.read_text().strip()
    assert tree.startswith("(") and tree.endswith(";")
