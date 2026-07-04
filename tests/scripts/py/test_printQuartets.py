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
