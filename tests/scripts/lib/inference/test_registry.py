import json
from pathlib import Path

import polars as pl

from scripts.lib.inference.inference import InferenceResult, TreeInferenceMethod
from scripts.lib.inference.registry import (
    compact,
    finalize_manifest,
    init_manifest,
    run_key,
    write_part,
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


def test_write_part_same_key_overwrites_cleanly(tmp_path: Path):
    parts = tmp_path / ".parts"
    r1 = _result("2026-01-01T00:00:00+00:00")
    r2 = _result("2026-01-02T00:00:00+00:00")
    assert run_key(r1) == run_key(r2)

    p1 = write_part(r1, parts)
    p2 = write_part(r2, parts)

    assert p1 == p2
    assert list(parts.glob("*.json")) == [p1]
    assert not list(parts.glob("*.tmp"))
    row = json.loads(p2.read_text())
    assert row["ran_at"] == "2026-01-02T00:00:00+00:00"


def test_different_config_hash_distinct_keys(tmp_path: Path):
    parts = tmp_path / ".parts"
    write_part(_result("2026-01-01T00:00:00+00:00", config_hash="x"), parts)
    write_part(_result("2026-01-01T00:00:00+00:00", config_hash="y"), parts)
    assert len(list(parts.glob("*.json"))) == 2


def test_compact_dedups_keeping_newest_ran_at(tmp_path: Path):
    parts = tmp_path / "inference_data" / ".parts"
    write_part(_result("2026-01-01T00:00:00+00:00"), parts)
    write_part(_result("2026-01-03T00:00:00+00:00"), parts)  # same key, newer
    write_part(_result("2026-01-02T00:00:00+00:00", replica=2), parts)  # distinct

    out = compact(tmp_path)
    df = pl.read_csv(out)
    assert df.height == 2
    newest = df.filter(pl.col("replica") == 1)["ran_at"].to_list()
    assert newest == ["2026-01-03T00:00:00+00:00"]


def test_compact_idempotent(tmp_path: Path):
    parts = tmp_path / "inference_data" / ".parts"
    write_part(_result("2026-01-01T00:00:00+00:00"), parts)

    out1 = compact(tmp_path)
    rows1 = pl.read_csv(out1).height
    # re-write same part + compact again
    write_part(_result("2026-01-01T00:00:00+00:00"), parts)
    out2 = compact(tmp_path)
    assert pl.read_csv(out2).height == rows1 == 1


def test_manifest_roundtrip(tmp_path: Path):
    init_manifest(tmp_path, ["mp"])
    finalize_manifest(tmp_path, 5)
    m = json.loads((tmp_path / "inference_data" / "manifest.json").read_text())
    assert m["methods"] == ["mp"]
    assert m["n_runs"] == 5
    assert m["created_at"] and m["completed_at"]
