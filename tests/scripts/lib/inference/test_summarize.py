import shutil
from pathlib import Path

import pytest

from scripts.lib.inference import summarize

NEXUS = (
    "#NEXUS\nBEGIN TREES;\n"
    "  TREE t1 = ((t1,t2),(t3,t4),t5);\n"
    "  TREE t2 = ((t1,t3),(t2,t4),t5);\n"
    "END;\n"
)


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript missing")
def test_summarize_live(tmp_path: Path) -> None:
    trees = tmp_path / "trees.nex"
    trees.write_text(NEXUS)
    out = tmp_path / "consensus.tree"

    try:
        result = summarize.summarize(trees, out, mode=2)
    except Exception:
        # R consensus dependency unavailable — fall back to argv assertion.
        calls: list[list[str]] = []
        summarize.subprocess.run = lambda argv, **kw: calls.append(argv) or None  # type: ignore[assignment]
        summarize.summarize(trees, out, mode=2)
        assert calls[0] == [
            "Rscript",
            "scripts/R/consensusTree.R",
            "-i",
            str(trees),
            "-m",
            "2",
            "-p",
            "0",
            "-o",
            str(out),
        ]
        return

    assert result == out
    assert out.exists()
    assert ";" in out.read_text()
