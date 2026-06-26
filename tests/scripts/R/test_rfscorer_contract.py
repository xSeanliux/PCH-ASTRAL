import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript not installed")
def test_rfscorer_stdout_is_single_fn_fp_line(tmp_path):
    # M0 contract: stdout is exactly one line `fn_rate fp_rate`; progress → stderr.
    est = tmp_path / "est.nwk"
    est.write_text("((t1,t2),(t3,t4),t5);\n")
    out = subprocess.run(
        [
            "Rscript", "scripts/R/RFScorer.R",
            "-i", str(est), "-f", "newick",
            "-r", "((t1,t2),(t3,t4),t5);", "-m", "1", "-p", "0",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    lines = out.stdout.strip().splitlines()
    assert len(lines) == 1, f"stdout must be one line, got {lines}"
    fn, fp = map(float, lines[0].split())
    assert fn == 0.0 and fp == 0.0  # identical trees
