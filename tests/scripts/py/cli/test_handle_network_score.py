import subprocess
from pathlib import Path

import polars as pl
import pytest

import scripts.py.cli.handle_network_score as hns
from scripts.lib.experiment import ExperimentConfig, MP4Config
from scripts.lib.inference.scoring import ScoreResult
from scripts.lib.model.methods import NetworkInferenceMethod
from scripts.py.cli.handle_network_score import handle_network_score
from scripts.py.cli.schemata import (
    INFERENCE_REGISTRY_SCHEMA,
    NETWORK_FAMILY_SCHEMA,
    NETWORK_SCORES_SCHEMA,
)

from tests.scripts.py.cli.test_handle_inference import _config

REF_TEXT = "((((A:1,B:1):1,C:1):1,(D:1,E:1):1):1,OUT:1)\nB;C;0.5;0.3\n"
NEWICKS = ["((((A,B),C),(D,E)),OUT);", "((((A,((B)#H1)),(#H1,C)),(D,E)),OUT);"]
# Real NetCS output: rerooted off the outgroup, leaving a unary `(OUT)`.
REROOTED = (
    "(t24,(t26,(((t27,(((((OUT),((((t14,t15),t11),t10),(t1,t2),(t4,t3))),"
    "(((t13,t12),t8),((t5,t6),t7))),((t30,t29),t16)))#H0),(t17,(t19,(t9,"
    "((((t28,t21),t23),((t20,t25),t18)),#H0))))),t22)));"
)


@pytest.mark.parametrize(
    ("newick", "label", "expected"),
    [
        ("(OUT,((a,(b)#H0),(c,(d,#H0))));", "OUT", True),
        ("(OUT,((a,b),(c,d)));", "OUT", True),
        ("((a,b),OUT);", "OUT", True),  # not the first root child
        (REROOTED, "OUT", False),
        ("((OUT),(a,b));", "OUT", False),  # unary root child is not the leaf
        ("(a,(OUT,b));", "OUT", False),
        ("(OUT2,(OUT,b));", "OUT", False),  # label is a prefix of another's
        ("(t10,(t1,b));", "t1", False),
        ("(t10,(t1,b));", "t10", True),
        ("(#H0,((a,(OUT)#H0),c));", "OUT", False),  # hybrid leaf at the root
    ],
)
def test_is_rooted_on(newick: str, label: str, expected: bool):
    assert hns.is_rooted_on(newick, label) is expected


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
        tmp_path
        / "inference_data"
        / "CAMUS"
        / "networks"
        / "sim_1_1_1.true_tree.family.csv"
    )
    family.parent.mkdir(parents=True)
    pl.DataFrame(
        {
            "edges_added": [0, 1],
            "network_newick": NEWICKS,
            "is_best": [True, True],
            "quartet_satisfied_percent": [0.0, 50.0],
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


def test_unguided_network_method_has_no_guide(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, monkeypatch)
    # A network method whose config has no guide_trees (none exists yet).
    monkeypatch.setitem(
        hns.METHOD_TO_CONFIG_CLASS, NetworkInferenceMethod.CAMUS, MP4Config
    )
    monkeypatch.setattr(hns, "score_network", lambda est, ref: ScoreResult(0, 0))
    df = pl.read_csv(handle_network_score(cfg), schema=NETWORK_SCORES_SCHEMA)
    assert df["guide_tree"].to_list() == [None, None]


@pytest.mark.parametrize(
    ("newick", "edges_added"),
    [
        ("(OUT,(((A,(B)#H0),#H0),((C)#H1,(D,(E,#H1)))));", 2),
        ("(OUT,((A,B),(C,D)));", 0),
    ],
)
def test_run_without_family_reads_point_estimate(
    tmp_path: Path, newick: str, edges_added: int
):
    run = dict.fromkeys(INFERENCE_REGISTRY_SCHEMA, None) | {
        "dataset_id": "d",
        "method": "netcs",
        "config_hash": "h",
        "method_config_json": "{}",
        "point_estimate_newick": newick,
        "status": "ok",
    }
    (tmp_path / "inference_data").mkdir()
    pl.DataFrame([run], schema=INFERENCE_REGISTRY_SCHEMA).write_csv(
        tmp_path / "inference_data" / "inference_registry.csv"
    )
    family = hns.read_families(tmp_path)
    assert family.select(list(NETWORK_FAMILY_SCHEMA)).rows() == [
        (edges_added, newick, True)
    ]
    assert family["guide_tree"].to_list() == [None]


def _register_point_estimate(tmp_path: Path, newick: str) -> None:
    """Make the registered run a NetCS one: no family, `newick` its point estimate."""
    reg = tmp_path / "inference_data" / "inference_registry.csv"
    pl.read_csv(reg, schema=INFERENCE_REGISTRY_SCHEMA).with_columns(
        method=pl.lit("netcs"),
        method_config_json=pl.lit("{}"),
        group_estimate_path=pl.lit(None, pl.String),
        point_estimate_newick=pl.lit(newick),
    ).write_csv(reg)


def test_network_off_the_outgroup_gets_null_rates(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, monkeypatch)
    _register_point_estimate(tmp_path, REROOTED)
    monkeypatch.setattr(hns, "score_network", lambda est, ref: pytest.fail("scored"))
    (row,) = pl.read_csv(handle_network_score(cfg), schema=NETWORK_SCORES_SCHEMA).rows(
        named=True
    )
    assert (row["fn_rate"], row["fp_rate"], row["status"]) == (None, None, "ok")


def test_camus_off_the_outgroup_is_scored(tmp_path: Path, monkeypatch):
    """CAMUS output is rooted; a hybrid outgroup is not a rooting failure."""
    cfg = _setup(tmp_path, monkeypatch)
    reg = tmp_path / "inference_data" / "inference_registry.csv"
    family = pl.read_csv(reg, schema=INFERENCE_REGISTRY_SCHEMA)["group_estimate_path"][
        0
    ]
    pl.read_csv(family).with_columns(network_newick=pl.lit(REROOTED)).write_csv(family)
    monkeypatch.setattr(hns, "score_network", lambda est, ref: ScoreResult(0.5, 0.25))
    df = pl.read_csv(handle_network_score(cfg), schema=NETWORK_SCORES_SCHEMA)
    assert df["fn_rate"].to_list() == [0.5, 0.5]


def test_network_is_scored_without_an_outgroup(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, monkeypatch)
    _register_point_estimate(tmp_path, REROOTED)
    graphs = tmp_path / "simulation_data" / "model_graph_registry.csv"
    pl.read_csv(graphs).with_columns(outgroup_label=pl.lit(None, pl.String)).write_csv(
        graphs
    )
    monkeypatch.setattr(hns, "score_network", lambda est, ref: ScoreResult(0.5, 0.25))
    (row,) = pl.read_csv(handle_network_score(cfg), schema=NETWORK_SCORES_SCHEMA).rows(
        named=True
    )
    assert (row["fn_rate"], row["fp_rate"], row["status"]) == (0.5, 0.25, "ok")


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


def test_reads_a_snaq_family(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, monkeypatch)
    newick = "(OUT,((C:1.2,(B)#H7:::0.8):0.5,((A,#H7:::0.2),(D,E):10.0)));"
    worse = "(OUT,((A,(B)#H7),((C,#H7),(D,E))));"  # same edges_added, not SNaQ's pick
    family = tmp_path / "inference_data" / "SNAQ" / "networks" / "sim.family.csv"
    family.parent.mkdir(parents=True)
    pl.DataFrame(
        {
            "edges_added": [1, 1],
            "network_newick": [newick, worse],
            "is_best": [True, False],
            "neg_loglik": [1.5, 2.5],
        }
    ).write_csv(family)
    reg = tmp_path / "inference_data" / "inference_registry.csv"
    camus = pl.read_csv(reg, schema=INFERENCE_REGISTRY_SCHEMA)
    snaq = camus.with_columns(
        method=pl.lit("snaq"),
        method_config_json=pl.lit('{"guide_trees":["mp"]}'),
        group_estimate_path=pl.lit(str(family)),
    )
    failed = snaq.with_columns(  # a failed run wrote nothing
        config_hash=pl.lit("failed"),
        status=pl.lit("failed"),
        group_estimate_path=pl.lit("missing.csv"),
    )
    tree = camus.with_columns(method=pl.lit("pch_wastral"))  # not a network
    pl.concat([camus, snaq, failed, tree]).write_csv(reg)
    seen: list[str] = []
    monkeypatch.setattr(
        hns, "score_network", lambda est, ref: seen.append(est) or ScoreResult(0, 0)
    )
    df = pl.read_csv(handle_network_score(cfg), schema=NETWORK_SCORES_SCHEMA)

    (row,) = df.filter(pl.col("method") == "snaq").rows(named=True)
    assert (row["edges_added"], row["guide_tree"], row["status"]) == (
        1,
        "mp",
        "ok",
    )
    assert worse not in seen
    assert seen[-1] == newick  # as written; score_network strips it


def test_two_best_per_edges_added_is_an_error(tmp_path: Path, monkeypatch):
    cfg = _setup(tmp_path, monkeypatch)
    (family,) = (tmp_path / "inference_data" / "CAMUS" / "networks").glob("*.csv")
    pl.DataFrame(
        {"edges_added": [1, 1], "network_newick": NEWICKS, "is_best": [True, True]}
    ).write_csv(family)
    with pytest.raises(ValueError, match="more than one is_best"):
        handle_network_score(cfg)
