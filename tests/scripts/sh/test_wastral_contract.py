import subprocess
from pathlib import Path

import pytest

from scripts.lib.pch import PCH_W
from scripts.lib.types import Dataset

ROOT = Path(__file__).resolve().parents[3]
WASTRAL = ROOT / "bin" / "wastral"
DS = (
    ROOT
    / "experiments/sample_experiment/simulation_data/simulated_data"
    / "high_0.0_4_320/sim_0_10_1.csv"
)


def _quartet_files(tmp_path):
    dataset = Dataset.from_path(DS)
    quartets = PCH_W.get_quartets(dataset)
    qf = tmp_path / "q.txt"
    wf = tmp_path / "w.txt"
    qf.write_text("".join(f"{q};\n" for q in quartets))
    wf.write_text("".join(f"{w}\n" for w in quartets.values()))
    return qf, wf


def _run(qf, wf, out, *, weighted):
    argv = [str(WASTRAL), "--mode", "4", "-i", str(qf), "-o", str(out)]
    if weighted:
        argv += ["--treeweights", str(wf)]
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return out.read_text().strip()


@pytest.mark.skipif(
    not (WASTRAL.exists() and DS.exists()),
    reason="wastral binary or sample dataset not available",
)
def test_wastral_mode4_applies_treeweights(tmp_path):
    # wASTRAL must run on PCH quartets-as-gene-trees, and --mode 4 must make the
    # per-quartet weights (--treeweights) actually affect the tree.
    qf, wf = _quartet_files(tmp_path)
    weighted = _run(qf, wf, tmp_path / "weighted.nwk", weighted=True)
    uniform = _run(qf, wf, tmp_path / "uniform.nwk", weighted=False)

    assert weighted.startswith("(") and weighted.endswith(";")
    assert weighted != uniform, "--treeweights had no effect (wrong mode?)"
