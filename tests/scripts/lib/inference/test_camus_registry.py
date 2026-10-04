from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest

from scripts.lib.inference import camus_registry
from scripts.lib.inference.inference import InferenceResult
from scripts.lib.model.methods import NetworkInferenceMethod, RunStatus
from scripts.py.cli.schemata import CAMUS_REGISTRY_SCHEMA

NEWICKS = [
    "(((A,B),(C,D)),OUT);",
    "(((A,(B)#H1),((#H1,C),D)),OUT);",
]
FAMILY = (
    "Number of Branches,Quartet Satisfied Percent,Extended Newick\n"
    f'0,0,"{NEWICKS[0]}"\n'
    f'1,36.86453576864536,"{NEWICKS[1]}"\n'
)


def _result(
    tmp_path: Path, family: str = FAMILY, ran_at: str | None = None
) -> InferenceResult:
    csv = tmp_path / "out" / "CAMUS" / "networks" / "sim_1_1_1.true_tree.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    csv.write_text(family)
    return InferenceResult(
        dataset_id="sim/sim_1_1_1.csv",
        method=NetworkInferenceMethod.CAMUS,
        config_hash="abc",
        method_config_json="{}",
        point_estimate_newick="",
        runtime_seconds=3.5,
        status=RunStatus.OK,
        ran_at=ran_at or datetime.now(timezone.utc).isoformat(),
        group_estimate_path=str(csv),
        log_path=str(tmp_path / "out" / "CAMUS" / "logs" / "sim_1_1_1.true_tree.log"),
    )


def test_write_family_appends_one_row_per_k(tmp_path: Path):
    shard = camus_registry.write_family(_result(tmp_path), "true_tree", tmp_path)
    assert shard.parent == camus_registry.get_shards_dir(tmp_path)
    assert len(shard.read_text().splitlines()) == 2


def test_compact_renames_columns_and_keeps_newicks_intact(tmp_path: Path):
    camus_registry.write_family(_result(tmp_path), "true_tree", tmp_path)
    out = camus_registry.compact(tmp_path)

    assert out == camus_registry.get_registry_path(tmp_path)
    df = pl.read_csv(out, schema=CAMUS_REGISTRY_SCHEMA).sort("k")
    assert df.columns == list(CAMUS_REGISTRY_SCHEMA.keys())
    assert df["k"].to_list() == [0, 1]
    assert df["qsat_percent"].to_list() == pytest.approx([0.0, 36.86453576864536])
    assert df["network_newick"].to_list() == NEWICKS
    assert df["guide_tree"].to_list() == ["true_tree"] * 2
    assert df["method"].to_list() == ["camus"] * 2
    assert "status" not in df.columns


def test_a_family_of_one_row_is_fine(tmp_path: Path):
    one = FAMILY.splitlines()[0] + "\n" + FAMILY.splitlines()[1] + "\n"
    camus_registry.write_family(_result(tmp_path, family=one), "true_tree", tmp_path)
    df = pl.read_csv(camus_registry.compact(tmp_path), schema=CAMUS_REGISTRY_SCHEMA)
    assert df["k"].to_list() == [0]


def test_write_family_rejects_unexpected_header(tmp_path: Path):
    bad = FAMILY.replace("Extended Newick", "Newick")
    with pytest.raises(ValueError, match="header"):
        camus_registry.write_family(
            _result(tmp_path, family=bad), "true_tree", tmp_path
        )
    assert not camus_registry.get_shards_dir(tmp_path).exists()


def test_write_family_rejects_a_missing_family(tmp_path: Path):
    result = _result(tmp_path)
    Path(str(result.group_estimate_path)).unlink()
    with pytest.raises(ValueError):
        camus_registry.write_family(result, "true_tree", tmp_path)


def test_write_family_rejects_an_empty_file(tmp_path: Path):
    result = _result(tmp_path, family="")
    with pytest.raises(ValueError):
        camus_registry.write_family(result, "true_tree", tmp_path)
    assert not camus_registry.get_shards_dir(tmp_path).exists()


def test_write_family_rejects_a_header_only_family(tmp_path: Path):
    result = _result(tmp_path, family=FAMILY.splitlines()[0] + "\n")
    with pytest.raises(ValueError, match="no rows"):
        camus_registry.write_family(result, "true_tree", tmp_path)
    assert not camus_registry.get_shards_dir(tmp_path).exists()


def test_write_family_rejects_a_torn_last_row(tmp_path: Path):
    torn = FAMILY.splitlines()[0] + "\n" + FAMILY.splitlines()[1] + "\n1,5\n"
    result = _result(tmp_path, family=torn)
    with pytest.raises(ValueError, match="null"):
        camus_registry.write_family(result, "true_tree", tmp_path)
    assert not camus_registry.get_shards_dir(tmp_path).exists()


def test_write_family_rejects_first_k_not_zero(tmp_path: Path):
    bad = FAMILY.splitlines()[0] + "\n" + FAMILY.splitlines()[2] + "\n"
    result = _result(tmp_path, family=bad)
    with pytest.raises(ValueError, match="k"):
        camus_registry.write_family(result, "true_tree", tmp_path)
    assert not camus_registry.get_shards_dir(tmp_path).exists()


def test_compact_dedups_a_requeued_family_keeping_the_newest(tmp_path: Path):
    camus_registry.write_family(
        _result(tmp_path, ran_at="2026-09-29T00:00:00+00:00"), "true_tree", tmp_path
    )
    camus_registry.compact(tmp_path)
    newer = FAMILY.replace("36.86453576864536", "40.0")
    camus_registry.write_family(
        _result(tmp_path, family=newer, ran_at="2026-09-29T01:00:00+00:00"),
        "true_tree",
        tmp_path,
    )
    df = pl.read_csv(camus_registry.compact(tmp_path), schema=CAMUS_REGISTRY_SCHEMA)
    assert df.height == 2
    assert df.filter(pl.col("k") == 1)["qsat_percent"][0] == pytest.approx(40.0)


def test_compact_dedups_by_family_not_by_k(tmp_path: Path):
    # A rerun that writes a SHORTER family must drop the earlier run's extra
    # (higher-k) rows too, not just update the k's the new family shares.
    three_rows = FAMILY + f'2,50.0,"{NEWICKS[1]}"\n'
    camus_registry.write_family(
        _result(tmp_path, family=three_rows, ran_at="2026-09-29T00:00:00+00:00"),
        "true_tree",
        tmp_path,
    )
    camus_registry.compact(tmp_path)  # 3 rows (k=0,1,2) from the first run

    camus_registry.write_family(
        _result(tmp_path, ran_at="2026-09-29T01:00:00+00:00"),  # 2 rows: k=0,1
        "true_tree",
        tmp_path,
    )
    df = pl.read_csv(camus_registry.compact(tmp_path), schema=CAMUS_REGISTRY_SCHEMA)

    assert df.height == 2
    assert df["ran_at"].to_list() == ["2026-09-29T01:00:00+00:00"] * 2


def test_compact_removes_shards(tmp_path: Path):
    camus_registry.write_family(_result(tmp_path), "true_tree", tmp_path)
    camus_registry.compact(tmp_path)
    assert not camus_registry.get_shards_dir(tmp_path).exists()
