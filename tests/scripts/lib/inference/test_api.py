import subprocess
from pathlib import Path
from typing import TextIO

import pytest

from scripts.lib.experiment import MP4Config
from scripts.lib.inference import api


def test_infer_ok(tmp_path: Path, monkeypatch) -> None:
    (runner,) = MP4Config().get_runners()
    out = tmp_path / "out"
    csv = tmp_path / "sim_0_1_1.csv"
    csv.write_text("id,feature,weight\n")

    def fake_run(argv, **kwargs):
        # Script success: write the expected point estimate.
        est = runner.get_point_estimate_path(out, csv.stem)
        est.parent.mkdir(parents=True, exist_ok=True)
        est.write_text("(a,(b,c));\n")

        class P:
            returncode = 0

        return P()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = api.infer(csv, out, runner)

    assert result.status == "ok"
    assert result.method == "mp"
    assert result.point_estimate_newick == "(a,(b,c));"
    assert result.runtime_seconds >= 0
    # Generic entry: identity is the input PATH, not the stem; no sim-key fields.
    assert result.dataset_id == str(csv)
    row = result.to_registry_row()
    assert row["dataset_id"] == str(csv)
    assert "poly_level" not in row and "fn_rate" not in row


def test_infer_logs_an_execute_exception_as_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (runner,) = MP4Config().get_runners()
    csv = tmp_path / "d.csv"

    def fake_run(
        argv: list[str], **_: int | TextIO
    ) -> subprocess.CompletedProcess[bytes]:
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = api.infer(csv, tmp_path, runner)
    assert result.status == "failed"
    assert "RuntimeError: boom" in runner.get_log_path(tmp_path, "d").read_text()


def test_default_execute_runs_build_argv_into_the_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (runner,) = MP4Config().get_runners()
    calls: list[tuple[list[str], int | TextIO]] = []

    def fake_run(
        argv: list[str], stdout: TextIO, **_: int | TextIO
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append((argv, stdout))
        return subprocess.CompletedProcess(argv, 3)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with (tmp_path / "log").open("w") as log:
        assert runner.execute("r", tmp_path / "d.csv", "d", tmp_path, log) == 3
    assert calls == [(runner.build_argv("r", tmp_path / "d.csv", "d", tmp_path), log)]
