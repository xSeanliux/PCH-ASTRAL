import subprocess
from pathlib import Path

import polars as pl
import pytest

import scripts.py.cli.handle_network_score as hns
from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference.scoring import NetworkScore
from scripts.py.cli.handle_network_score import handle_network_score
from scripts.py.cli.schemata import CAMUS_REGISTRY_SCHEMA, NETWORK_SCORES_SCHEMA

from tests.scripts.py.cli.test_handle_inference import _config

REF_TEXT = "((((A:1,B:1):1,C:1):1,(D:1,E:1):1):1,OUT:1)\nB;C;0.5;0.3\n"
NEWICKS = ["((((A,B),C),(D,E)),OUT);", "((((A,((B)#H1)),(#H1,C)),(D,E)),OUT);"]


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ExperimentConfig:
    jar = tmp_path / "PhyloNet.jar"
    jar.touch()
    monkeypatch.setattr(hns, "PHYLONET_JAR", jar)
    sim_dir = tmp_path / "simulation_data" / "simulated_data" / "high_0.1_4_320"
    sim_dir.mkdir(parents=True)
    dataset = sim_dir / "sim_1_1_1.csv"
    dataset.write_text("id,feature,weight,A,B,C,D,E,OUT\n")
    net = tmp_path / "simulation_data" / "net1-1.txt"
    net.write_text(REF_TEXT)
    pl.DataFrame(
        {
            "horizontal_edges": [1],
            "model_tree": [1],
            "path": [str(net)],
            "outgroup": ["OUT"],
            "outgroup_seed": [1],
            "outgroup_branch_length": [1.0],
            "ingroup_stem_length": [1.0],
        }
    ).write_csv(tmp_path / "simulation_data" / "model_graph_registry.csv")
    pl.DataFrame(
        {
            "poly_level": ["high"],
            "character_count": [320],
            "min_tree_height": [4],
            "homoplasy_factor": [0.1],
            "horizontal_edges": [1],
            "model_tree": [1],
            "replica": [1],
            "path": [str(dataset)],
        }
    ).write_csv(tmp_path / "simulation_data" / "simulated_data_registry.csv")
    (tmp_path / "inference_data").mkdir()
    pl.DataFrame(
        {
            "dataset_id": [str(dataset)] * 2,
            "method": ["camus"] * 2,
            "guide_tree": ["true_tree"] * 2,
            "config_hash": ["h"] * 2,
            "ran_at": ["2026-09-29T00:00:00+00:00"] * 2,
            "k": [0, 1],
            "qsat_percent": [0.0, 50.0],
            "network_newick": NEWICKS,
        },
        schema=CAMUS_REGISTRY_SCHEMA,
    ).write_csv(tmp_path / "inference_data" / "camus_registry.csv")
    return ExperimentConfig.model_validate(
        _config(tmp_path, methods={"camus": {"guide_trees": ["true_tree"]}})
    )


def test_writes_scores(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, monkeypatch)
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        hns,
        "score_network",
        lambda est, ref: seen.append((est, ref)) or NetworkScore(0.5, 0.0),
    )
    out = handle_network_score(cfg)

    df = pl.read_csv(out, schema=NETWORK_SCORES_SCHEMA).sort("k")
    assert df.columns == list(NETWORK_SCORES_SCHEMA.keys())
    assert df["k"].to_list() == [0, 1]
    assert df["fp_rate"].to_list() == [0.0, 0.0]
    assert df["method"].to_list() == ["camus", "camus"]
    assert df["guide_tree"].to_list() == ["true_tree", "true_tree"]
    assert df["fn_rate"].to_list() == [0.5, 0.5]
    assert df["status"].to_list() == ["ok", "ok"]
    assert all(t >= 0 for t in df["runtime_seconds"].to_list())
    assert [e for e, _ in seen] == NEWICKS
    assert {r for _, r in seen} == {"((((A,((B)#H2,#H1)),((C)#H1,#H2)),(D,E)),OUT);"}
    # Scoring is its own stage: reads the family registry, writes one file.
    assert {p.name for p in (tmp_path / "inference_data").iterdir()} == {
        "camus_registry.csv",
        "network_scores.csv",
    }


def test_missing_jar_stops_before_scoring(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, monkeypatch)
    hns.PHYLONET_JAR.unlink()
    with pytest.raises(AssertionError, match="install-phylonet"):
        handle_network_score(cfg)
    assert not (tmp_path / "inference_data" / "network_scores.csv").exists()


def test_interrupt_keeps_scored_rows(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, monkeypatch)
    calls: list[int] = []

    def fake(est: str, ref: str) -> NetworkScore:
        calls.append(1)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return NetworkScore(0.5, 0.0)

    monkeypatch.setattr(hns, "score_network", fake)
    with pytest.raises(KeyboardInterrupt):
        handle_network_score(cfg)
    assert pl.read_csv(tmp_path / "inference_data" / "network_scores.csv").height == 1


def test_incremental(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, monkeypatch)
    calls: list[int] = []
    monkeypatch.setattr(
        hns,
        "score_network",
        lambda est, ref: calls.append(1) or NetworkScore(0.5, 0.0),
    )
    handle_network_score(cfg)
    handle_network_score(cfg)
    assert len(calls) == 2
    assert pl.read_csv(tmp_path / "inference_data" / "network_scores.csv").height == 2


def test_timeout_and_failure_rows(tmp_path: Path, monkeypatch, capsys):
    cfg = _setup(tmp_path, monkeypatch)

    def fake(est: str, ref: str) -> NetworkScore:
        if "#H1" in est:
            raise subprocess.TimeoutExpired(["java"], 7200)
        raise RuntimeError("boom")

    monkeypatch.setattr(hns, "score_network", fake)
    out = handle_network_score(cfg)

    df = pl.read_csv(out, schema=NETWORK_SCORES_SCHEMA).sort("k")
    assert df["status"].to_list() == ["failed", "timeout"]
    assert df["fn_rate"].to_list() == [None, None]
    assert df["runtime_seconds"].null_count() == 0
    assert "boom" in capsys.readouterr().out

    # Not retried: the rows are visible, so the next run leaves them alone.
    monkeypatch.setattr(hns, "score_network", lambda est, ref: pytest.fail("retried"))
    handle_network_score(cfg)
