import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SAMPLE = ROOT / "tests/scripts/lib/sample_dataset.csv"


def test_quartet_gen_runs():
    # M0 regression: `-m` module invocation must work and `from_path` needs a Path.
    out = subprocess.run(
        [sys.executable, "-m", "scripts.py.printQuartets", "-i", str(SAMPLE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip(), "expected quartets on stdout"
    assert ";" in out.stdout  # ASTRAL3 newick format


def test_quartet_order_ignores_hash_seed(tmp_path: Path):
    """Quartet order must not depend on ``PYTHONHASHSEED``."""
    # SAMPLE yields one quartet; 4 taxa per state yield 36.
    csv = tmp_path / "d.csv"
    csv.write_text("id,feature,weight,a,b,c,d,e,f,g,h\nx,y,1,1,1,1,1,2,2,2,2\n")
    outs = [
        subprocess.run(
            [sys.executable, "-m", "scripts.py.printQuartets", "-i", str(csv)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        ).stdout
        for seed in ("0", "1")
    ]
    assert outs[0] == outs[1]
