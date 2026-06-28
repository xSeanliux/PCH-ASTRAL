import json
from pathlib import Path

import polars as pl

from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod
from scripts.lib.inference.registry import (
    compact,
    finalize_manifest,
    init_manifest,
    run_key,
    write_result,
)


def _result(
    ran_at: str, *, replica: int = 1, config_hash: str = "abc"
) -> InferenceResult:
    return InferenceResult(
        dataset_id="ds1",
        tree_inference_method=TreeInferenceMethod.MP,
        config_hash=config_hash,
        method_config_json="{}",
        point_estimate_newick="(a,b);",
        runtime_seconds=1.0,
        status="ok",
        ran_at=ran_at,
        homoplasy_factor=0.1,
        tree_height=4,
        n_chars=320,
        ret_edges=0,
        target_tree=1,
        replica=replica,
    )


def test_run_key_is_human_readable():
    k = run_key(_result("2026-01-01T00:00:00+00:00").to_registry_row())
    assert "ds1" in k and "mp" in k and "abc" in k  # readable, not an opaque hash


def test_write_result_appends_to_shard(tmp_path: Path):
    write_result(_result("2026-01-01T00:00:00+00:00"), tmp_path)
    write_result(_result("2026-01-02T00:00:00+00:00", replica=2), tmp_path)
    shards = list((tmp_path / "inference_data" / "shards").glob("*.jsonl"))
    assert len(shards) == 1  # one shard per process
    assert len(shards[0].read_text().splitlines()) == 2


def test_compact_dedups_keeping_newest_ran_at(tmp_path: Path):
    write_result(_result("2026-01-01T00:00:00+00:00"), tmp_path)
    write_result(_result("2026-01-03T00:00:00+00:00"), tmp_path)  # same key, newer
    write_result(_result("2026-01-02T00:00:00+00:00", replica=2), tmp_path)  # distinct
    df = pl.read_csv(compact(tmp_path))
    assert df.height == 2
    assert df.filter(pl.col("replica") == 1)["ran_at"].to_list() == [
        "2026-01-03T00:00:00+00:00"
    ]


def test_different_config_hash_distinct(tmp_path: Path):
    write_result(_result("2026-01-01T00:00:00+00:00", config_hash="x"), tmp_path)
    write_result(_result("2026-01-01T00:00:00+00:00", config_hash="y"), tmp_path)
    assert pl.read_csv(compact(tmp_path)).height == 2


def test_compact_cleans_up_shards(tmp_path: Path):
    write_result(_result("2026-01-01T00:00:00+00:00"), tmp_path)
    compact(tmp_path)
    shards = tmp_path / "inference_data" / "shards"
    assert not shards.exists() or not list(shards.glob("*.jsonl"))


def test_compact_accumulates_across_cleanups(tmp_path: Path):
    # Shards are deleted after each compact; the registry must still accumulate.
    write_result(_result("2026-01-01T00:00:00+00:00", replica=1), tmp_path)
    compact(tmp_path)
    write_result(_result("2026-01-02T00:00:00+00:00", replica=2), tmp_path)
    df = pl.read_csv(compact(tmp_path))
    assert df.height == 2  # replica 1 from prior registry + replica 2 from new shard


def test_manifest_roundtrip(tmp_path: Path):
    init_manifest(tmp_path, ["mp"])
    finalize_manifest(tmp_path, 5)
    m = json.loads((tmp_path / "inference_data" / "manifest.json").read_text())
    assert m["methods"] == ["mp"]
    assert m["n_runs"] == 5
    assert m["created_at"] and m["completed_at"]
