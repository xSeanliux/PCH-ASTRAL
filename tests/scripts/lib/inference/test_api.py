from pathlib import Path

from scripts.lib.inference import api, runners
from scripts.lib.inference.inference import TreeInferenceMethod
from scripts.lib.inference.methods import resolve_config


def test_infer_ok(tmp_path: Path, monkeypatch) -> None:
    method = TreeInferenceMethod.MP
    out = tmp_path / "out"
    csv = tmp_path / "sim_0_1_1.csv"
    csv.write_text("id,feature,weight\n")

    def fake_run(argv, **kwargs):
        # Script success: write the expected point estimate.
        est = runners.point_estimate_path(method, out, csv.stem)
        est.parent.mkdir(parents=True, exist_ok=True)
        est.write_text("(a,(b,c));\n")

        class P:
            returncode = 0

        return P()

    monkeypatch.setattr(api.subprocess, "run", fake_run)

    result = api.infer(csv, out, method, resolve_config(method, None))

    assert result.status == "ok"
    assert result.tree_inference_method == "mp"
    assert result.point_estimate_newick == "(a,(b,c));"
    assert result.runtime_seconds >= 0
