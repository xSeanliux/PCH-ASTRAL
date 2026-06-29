import json
from pathlib import Path

from typer.testing import CliRunner

import scripts.py.cli.main as main
from scripts.lib.inference.scoring import ScoreResult

runner = CliRunner()


def test_score_cmd(tmp_path: Path, monkeypatch):
    est = tmp_path / "est.txt"
    ref = tmp_path / "ref.txt"
    est.write_text("(A,B);")
    ref.write_text("(A,B);")
    seen = {}

    def fake_score(e, r):
        seen["args"] = (e, r)
        return ScoreResult(0.1, 0.2)

    monkeypatch.setattr(main, "score", fake_score)
    res = runner.invoke(
        main.app,
        ["score", "--estimate", str(est), "--reference", str(ref), "--json"],
    )
    assert res.exit_code == 0, res.output
    assert seen["args"] == ("(A,B);", "(A,B);")
    assert json.loads(res.output) == {"fn_rate": 0.1, "fp_rate": 0.2}


def test_summarize_cmd(tmp_path: Path, monkeypatch):
    trees = tmp_path / "trees.txt"
    trees.write_text("(A,B);\n")
    out = tmp_path / "cons.txt"
    seen = {}

    def fake_summarize(t, o, *, mode, discard):
        seen.update(mode=mode, discard=discard)
        return o

    monkeypatch.setattr(main, "summarize", fake_summarize)
    res = runner.invoke(
        main.app,
        [
            "summarize",
            "--trees",
            str(trees),
            "--output",
            str(out),
            "--consensus",
            "mcc",
            "--discard",
            "10",
        ],
    )
    assert res.exit_code == 0, res.output
    assert seen == {"mode": 4, "discard": 10}
    assert "cons.txt" in res.output
