import subprocess
from pathlib import Path

import polars as pl
import pytest

import scripts.py.cli.handle_network_score as hns
from scripts.lib.experiment import ExperimentConfig
from scripts.lib.inference.scoring import ScoreResult
from scripts.py.cli.handle_network_score import handle_network_score
from scripts.py.cli.schemata import INFERENCE_REGISTRY_SCHEMA, NETWORK_SCORES_SCHEMA

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
            "outgroup_label": ["OUT"],
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
    family = (
        tmp_path / "inference_data" / "CAMUS" / "networks" / "sim_1_1_1.true_tree.csv"
    )
    family.parent.mkdir(parents=True)
    pl.DataFrame(
        {
            "Number of Branches": [0, 1],
            "Quartet Satisfied Percent": [0.0, 50.0],
            "Extended Newick": NEWICKS,
        }
    ).write_csv(family)
    run = dict.fromkeys(INFERENCE_REGISTRY_SCHEMA, None) | {
        "dataset_id": str(dataset),
        "method": "camus",
        "config_hash": "h",
        "method_config_json": '{"guide_trees":["true_tree"],"outgroup_label":"OUT"}',
        "group_estimate_path": str(family),
        "status": "ok",
    }
    pl.DataFrame([run], schema=INFERENCE_REGISTRY_SCHEMA).write_csv(
        tmp_path / "inference_data" / "inference_registry.csv"
    )
    return ExperimentConfig.model_validate(
        _config(
            tmp_path,
            methods={"camus": {"guide_trees": ["true_tree"], "outgroup_label": "OUT"}},
        )
    )


def test_writes_scores(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, monkeypatch)
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        hns,
        "score_network",
        lambda est, ref: seen.append((est, ref)) or ScoreResult(0.5, 0.0),
    )
    out = handle_network_score(cfg)

    df = pl.read_csv(out, schema=NETWORK_SCORES_SCHEMA).sort("edges_added")
    assert df.columns == list(NETWORK_SCORES_SCHEMA.keys())
    assert df["edges_added"].to_list() == [0, 1]
    assert df["fp_rate"].to_list() == [0.0, 0.0]
    assert df["method"].to_list() == ["camus", "camus"]
    assert df["guide_tree"].to_list() == ["true_tree", "true_tree"]
    assert df["fn_rate"].to_list() == [0.5, 0.5]
    assert df["status"].to_list() == ["ok", "ok"]
    assert all(t >= 0 for t in df["runtime_seconds"].to_list())
    assert [e for e, _ in seen] == NEWICKS
    assert {r for _, r in seen} == {"((((A,((B)#H2,#H1)),((C)#H1,#H2)),(D,E)),OUT);"}
    # Scoring is its own stage: reads the families, writes one file.
    assert {p.name for p in (tmp_path / "inference_data").iterdir()} == {
        "CAMUS",
        "inference_registry.csv",
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

    def fake(est: str, ref: str) -> ScoreResult:
        calls.append(1)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return ScoreResult(0.5, 0.0)

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
        lambda est, ref: calls.append(1) or ScoreResult(0.5, 0.0),
    )
    handle_network_score(cfg)
    handle_network_score(cfg)
    assert len(calls) == 2
    assert pl.read_csv(tmp_path / "inference_data" / "network_scores.csv").height == 2


def test_timeout_and_failure_rows(tmp_path: Path, monkeypatch, capsys):
    cfg = _setup(tmp_path, monkeypatch)

    def fake(est: str, ref: str) -> ScoreResult:
        if "#H1" in est:
            raise subprocess.TimeoutExpired(["java"], 7200)
        raise RuntimeError("boom")

    monkeypatch.setattr(hns, "score_network", fake)
    out = handle_network_score(cfg)

    df = pl.read_csv(out, schema=NETWORK_SCORES_SCHEMA).sort("edges_added")
    assert df["status"].to_list() == ["failed", "timeout"]
    assert df["fn_rate"].to_list() == [None, None]
    assert df["runtime_seconds"].null_count() == 0
    assert "boom" in capsys.readouterr().out

    # Not retried: the rows are visible, so the next run leaves them alone.
    monkeypatch.setattr(hns, "score_network", lambda est, ref: pytest.fail("retried"))
    handle_network_score(cfg)


def test_scores_a_snaq_network_without_annotations(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, monkeypatch)
    newick = "(OUT,((C:1.2,(B)#H7:::0.8):0.5,((A,#H7:::0.2),(D,E):10.0)));"
    reg = tmp_path / "inference_data" / "inference_registry.csv"
    camus = pl.read_csv(reg, schema=INFERENCE_REGISTRY_SCHEMA)
    snaq = camus.with_columns(
        method=pl.lit("snaq"),
        method_config_json=pl.lit("{}"),
        point_estimate_newick=pl.lit(newick),
    )
    failed = snaq.with_columns(  # a failed run wrote nothing
        config_hash=pl.lit("failed"), status=pl.lit("failed")
    )
    tree = camus.with_columns(method=pl.lit("pch_wastral"))  # not a network
    pl.concat([camus, snaq, failed, tree]).write_csv(reg)
    seen: list[str] = []
    monkeypatch.setattr(
        hns, "score_network", lambda est, ref: seen.append(est) or ScoreResult(0, 0)
    )
    df = pl.read_csv(handle_network_score(cfg), schema=NETWORK_SCORES_SCHEMA)

    row = df.filter(pl.col("method") == "snaq").row(0, named=True)
    assert (row["edges_added"], row["guide_tree"], row["status"]) == (1, None, "ok")
    assert seen[-1] == "(OUT,((C,(B)#H7),((A,#H7),(D,E))));"
