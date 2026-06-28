import shutil
import types
from pathlib import Path

import pytest

from scripts.lib.inference import summarize

NEXUS = (
    "#NEXUS\nBEGIN TREES;\n"
    "  TREE t1 = ((t1,t2),(t3,t4),t5);\n"
    "  TREE t2 = ((t1,t3),(t2,t4),t5);\n"
    "END;\n"
)


def test_summarize_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trees = tmp_path / "trees.nex"
    trees.write_text(NEXUS)
    out = tmp_path / "consensus.tree"

    calls: list[list[str]] = []

    def fake_run(argv, **kw):
        calls.append(argv)
        out.write_text(";\n")
        return types.SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(summarize.subprocess, "run", fake_run)

    result = summarize.summarize(trees, out, mode=2)
    assert result == out
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


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript missing")
def test_summarize_live(tmp_path: Path) -> None:
    trees = tmp_path / "trees.nex"
    trees.write_text(NEXUS)
    out = tmp_path / "consensus.tree"

    result = summarize.summarize(trees, out, mode=2)
    assert result == out
    assert out.exists()
    assert ";" in out.read_text()
